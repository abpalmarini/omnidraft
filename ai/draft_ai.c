#include <stdio.h>
#include <omp.h>

#include "draft_ai.h"


// sizes
int num_heroes;
int num_synergy_rs;
int num_counter_rs;
int draft_len;

// rewards
struct role_r role_rs[MAX_NUM_HEROES];
struct synergy_r synergy_rs[MAX_SYNERGY_RS];
struct counter_r counter_rs[MAX_COUNTER_RS];

// info needed to update legal actions
struct h_info h_infos[MAX_NUM_HEROES];

// team selecting and selection type for each stage in draft
struct draft_stage draft[MAX_DRAFT_LEN]; 

// random bitstrings for each hero being picked by team A, picked
// by team B, or being banned by either team (used to track and
// identify unique states--see wikipedia.org/wiki/Zobrist_hashing)
u64 zobrist_keys[3][MAX_NUM_HEROES];

// set by run_search and used for evaluating multiple lineup
// terminal values in flex_negamax
int root_selecting_team;

// transposition table
struct tt_entry tt[TT_IDX_BITS + 1];


//
// Fast Negamax search algorithm for drafting.
//
// Heroes (numbered based on reward potential and given a different
// number for each role they play) are represented by a bit in the
// teams and legal actions. These are swapped around and updated with
// each recursive call, eliminating the need to track teams or undo
// state. A bitwise OR between a team and hero (retrieved by shifting
// 1 by the hero's index num) will add the hero to the team. A bitwise
// AND between a hero and legal actions will determine if it is
// available. A bitwise AND between legal actions and all heroes that
// play a different role (for picks) or are not the same underlying
// hero (for bans and enemy picks) will turn any still legal heroes
// illegal. Additionally, synergies and counters can be evaluated by
// comparing the reward heroes to the bitwise AND between themselves
// and some team.
//
int negamax(
    u64 team,         // selecting team bit string
    u64 e_team,
    u64 legal,
    u64 e_legal,
    int rr_value,
    u64 hash,
    int stage,
    int alpha,
    int beta
)
{
    if (stage == draft_len)
        // since B has last pick in draft it is always
        // guaranteed that team is A and e_team is B
        return rr_value + terminal_value(team, e_team);

    int original_alpha = alpha;

    if (stage < MAX_TT_STAGE) {
        struct tt_entry tt_entry = tt[hash & TT_IDX_BITS];

        // check if state has already been evaluated
        // and stored in the transposition table
        if (tt_entry.tag == (hash >> 18)) {     // tag equal to upper 46 bits of hash
            int value = tt_entry.value;
            switch (tt_entry.flag)  {
                case EXACT:
                    return value;

                case LOWERBOUND:
                    if (value > alpha)
                        alpha = value;
                    break;

                case UPPERBOUND:
                    if (value < beta)
                        beta = value;
                    break;
            }

            if (alpha >= beta)
                return value;
        }
    }

    int value = -INF;
    switch (draft[stage].selection) {
        case PICK:
            for (int h = 0; h < num_heroes; h++) {
                // check hero is in selecting team's legal actions
                if (!(legal & (1ULL << h)))
                    continue;

                // switch teams and legal actions around
                // after updating them for next stage
                int child_value = -negamax(
                    e_team,
                    team | (1ULL << h),
                    e_legal & h_infos[h].diff_h,
                    legal & h_infos[h].diff_role_and_h,
                    rr_value + (draft[stage].team == A ? role_rs[h].A_value : -role_rs[h].B_value),
                    hash ^ zobrist_keys[draft[stage].team][h],
                    stage + 1,
                    -beta,
                    -alpha
                );

                if (child_value > value)
                    value = child_value;

                if (value > alpha)
                    alpha = value;

                if (alpha >= beta)
                    goto cutoff;    // used for consitency with double selections
            }                       // a normal break would work fine here
            break;

        case BAN:
            for (int h = 0; h < num_heroes; h++) {
                // save time searching redundant states by only
                // considering to ban heroes the enemies can pick
                if (!(e_legal & (1ULL << h)))
                    continue;

                int child_value = -negamax(
                    e_team,
                    team,
                    e_legal & h_infos[h].diff_h,
                    legal & h_infos[h].diff_h,
                    rr_value,
                    hash ^ zobrist_keys[BAN_KEYS][h],
                    stage + 1,
                    -beta,
                    -alpha
                );

                if (child_value > value)
                    value = child_value;

                if (value > alpha)
                    alpha = value;

                if (alpha >= beta)
                    goto cutoff;
            }
            break;

        case PICK_PICK:
            for (int h = 0; h < num_heroes; h++) {
                if (!(legal & (1ULL << h)))
                    continue;

                u64 new_team = team | (1ULL << h);
                u64 new_legal = legal & h_infos[h].diff_role_and_h;
                u64 new_e_legal = e_legal & h_infos[h].diff_h;
                int new_rr_value = rr_value + (draft[stage].team == A ? role_rs[h].A_value : -role_rs[h].B_value);
                u64 new_hash = hash ^ zobrist_keys[draft[stage].team][h];

                // order in double pick is irrelevant
                // so earlier pairs can be skipped
                for (int h2 = h + 1; h2 < num_heroes; h2++) {
                    if (!(new_legal & (1ULL << h2)))
                        continue;

                    int child_value = -negamax(
                        e_team,
                        new_team | (1ULL << h2),
                        new_e_legal & h_infos[h2].diff_h,
                        new_legal & h_infos[h2].diff_role_and_h,
                        new_rr_value + (draft[stage].team == A ? role_rs[h2].A_value : -role_rs[h2].B_value),
                        new_hash ^ zobrist_keys[draft[stage].team][h2],
                        stage + 2,
                        -beta,
                        -alpha
                    );

                    if (child_value > value)
                        value = child_value;

                    if (value > alpha)
                        alpha = value;

                    if (alpha >= beta)
                        goto cutoff;
                }
            }
            break;

        case PICK_BAN:
            for (int h = 0; h < num_heroes; h++) {
                if (!(legal & (1ULL << h)))
                    continue;

                u64 new_team = team | (1ULL << h);
                u64 new_legal = legal & h_infos[h].diff_role_and_h;
                u64 new_e_legal = e_legal & h_infos[h].diff_h;
                int new_rr_value = rr_value + (draft[stage].team == A ? role_rs[h].A_value : -role_rs[h].B_value);
                u64 new_hash = hash ^ zobrist_keys[draft[stage].team][h];

                // order of selections matter here
                for (int h2 = 0; h2 < num_heroes; h2++) {
                    // also switch to enemy legals for ban
                    if (!(new_e_legal & (1ULL << h2)))
                        continue;

                    int child_value = -negamax(
                        e_team,
                        new_team,
                        new_e_legal & h_infos[h2].diff_h,
                        new_legal & h_infos[h2].diff_h,
                        new_rr_value,
                        new_hash ^ zobrist_keys[BAN_KEYS][h2],
                        stage + 2,
                        -beta,
                        -alpha
                    );

                    if (child_value > value)
                        value = child_value;

                    if (value > alpha)
                        alpha = value;

                    if (alpha >= beta)
                        goto cutoff;
                }
            }
            break;

        case BAN_PICK:
            for (int h = 0; h < num_heroes; h++) {
                if (!(e_legal & (1ULL << h)))
                    continue;

                u64 new_legal = legal & h_infos[h].diff_h;
                u64 new_e_legal = e_legal & h_infos[h].diff_h;
                u64 new_hash = hash ^ zobrist_keys[BAN_KEYS][h];

                // again: order of selection matters
                for (int h2 = 0; h2 < num_heroes; h2++) {
                    // switch to selecting team legal actions for pick
                    if (!(new_legal & (1ULL << h2)))
                        continue;

                    int child_value = -negamax(
                        e_team,
                        team | (1ULL << h2),
                        new_e_legal & h_infos[h2].diff_h,
                        new_legal & h_infos[h2].diff_role_and_h,
                        rr_value + (draft[stage].team == A ? role_rs[h2].A_value : -role_rs[h2].B_value),
                        new_hash ^ zobrist_keys[draft[stage].team][h2],
                        stage + 2,
                        -beta,
                        -alpha
                    );

                    if (child_value > value)
                        value = child_value;

                    if (value > alpha)
                        alpha = value;

                    if (alpha >= beta)
                        goto cutoff;
                }
            }
            break;

        case BAN_BAN:
            for (int h = 0; h < num_heroes; h++) {
                if (!(e_legal & (1ULL << h)))
                    continue;

                u64 new_legal = legal & h_infos[h].diff_h;
                u64 new_e_legal = e_legal & h_infos[h].diff_h;
                u64 new_hash = hash ^ zobrist_keys[BAN_KEYS][h];

                // order for double bans is irrelevant
                for (int h2 = h + 1; h2 < num_heroes; h2++) {
                    if (!(new_e_legal & (1ULL << h2)))
                        continue;

                    int child_value = -negamax(
                        e_team,
                        team,
                        new_e_legal & h_infos[h2].diff_h,
                        new_legal & h_infos[h2].diff_h,
                        rr_value,
                        new_hash ^ zobrist_keys[BAN_KEYS][h2],
                        stage + 2,
                        -beta,
                        -alpha
                    );

                    if (child_value > value)
                        value = child_value;

                    if (value > alpha)
                        alpha = value;

                    if (alpha >= beta)
                        goto cutoff;

                }
            }
            break;
    }

cutoff:
    
    if (stage < MAX_TT_STAGE) {
        // pack state value, flag and tag into 64 bits (upper 46 bits of hash for tag,
        // 2 bits for flag and 16 bits for value) then store in transposition table
        if (value <= original_alpha)
            tt[hash & TT_IDX_BITS] = (struct tt_entry) {(hash >> 18), UPPERBOUND, value};
        else if (value >= beta)
            tt[hash & TT_IDX_BITS] = (struct tt_entry) {(hash >> 18), LOWERBOUND, value};
        else
            tt[hash & TT_IDX_BITS] = (struct tt_entry) {(hash >> 18), EXACT, value};
    }

    return value;
}


// 
// Evaluate synergy and counter rewards from team A's perspective. 
// (Role rewards are tracked as the tree is traversed).
//
int terminal_value(u64 team_A, u64 team_B)
{
    int value = 0;

    // synergies
    for (int i = 0; i < num_synergy_rs; i++) {
        u64 s_heroes = synergy_rs[i].heroes;

        // if all synergy heroes are part of a team then
        // the AND between the two will equal the original
        if ((team_A & s_heroes) == s_heroes)
            value += synergy_rs[i].A_value;
        else if ((team_B & s_heroes) == s_heroes)
            value -= synergy_rs[i].B_value;
    }

    // counters
    for (int i = 0; i < num_counter_rs; i++) {
        u64 c_heroes = counter_rs[i].heroes;
        u64 c_foes = counter_rs[i].foes;

        // same deal as synergies except reward is only
        // granted if opposition also have specified heroes
        if ((team_A & c_heroes) == c_heroes && (team_B & c_foes) == c_foes)
            value += counter_rs[i].A_value;
        else if ((team_B & c_heroes) == c_heroes && (team_A & c_foes) == c_foes)
            value -= counter_rs[i].B_value;
    }

    return value;
}


//
// To eliminate searching redundant states that contain teams
// with more than one hero per role, all heroes who play a filled
// role are treated as illegal. To generate these legal actions
// fast a hero who plays more than one role is treated as two
// different heroes. This works fine when the starting state does
// not contain any flex heroes. If, however, the enemy selected
// hero X in the real draft and X plays two roles then we must
// consider the enemy playing X in either role. It is therefore
// possible for teams to have multiple starting lineups. It is
// not okay to just run search for each lineup combination as
// the optimal action vs one enemy lineup may not be optimal for
// another.
//
// This function considers the same action being taken across
// all applicable lineups (multiple locations of the global tree)
// until it can hand over to normal negamax. This ensures the
// optimal value is returned no matter what teams select or what
// roles they choose to play their heroes in throughout the rest
// of the draft.
//
int flex_negamax(
    int num_teams,
    int num_e_teams,
    u64 teams[],
    u64 e_teams[],
    u64 legals[],
    u64 e_legals[],
    int rr_values[],
    int e_rr_values[],
    u64 hashes[],
    u64 e_hashes[],
    u64 bans_hash,
    int stage,
    int alpha,
    int beta
)
{
    if (num_e_teams == 1) {
        // if enemy can't swtich lineups then value is highest the
        // selecting team can achieve with one of its lineups vs it
        int value = -INF;

        for (int i = 0; i < num_teams; i++) {
            int team_value = negamax(    // switch to normal negamax
                teams[i],
                e_teams[0],
                legals[i],
                e_legals[0],
                rr_values[i] + e_rr_values[0],
                bans_hash ^ hashes[i] ^ e_hashes[0],    // final hash is XOR of all selections
                stage,
                alpha,
                beta
            );

            if (team_value > value)
                value = team_value;

            if (value > alpha)
                alpha = value;

            // can skip other lineups if enemy has better options
            if (alpha >= beta)
                break;
        }

        return value;
    } else if (stage == draft_len) {
        // Need to find terminal value when teams have multiple lineups.
        // In most cases each team will have a preferred lineup that is
        // independent of the enemy lineup used. However, with the ability
        // to specify specific roles for adversaries in counter rewards,
        // this may not always be the case. It could be possible for teams
        // to alternate indefinitely in unilaterally changing the roles
        // they play their heroes in to exploit the enemy composition and
        // gain more value (the game is not over when drafting finishes).
        // As the value doesn't converge the best guaranteed value for the
        // selecting team is returned. This ensures consistency with what
        // would have been decided in earlier searches. This is because
        // each lineup vs lineup can only have one value, but if the
        // optimal value returned was found from following a lineup that
        // leads to this situation then it must have assumed the best
        // enemy response. This would have also resulted in more value for
        // the selecting team than when considering one of the alternate
        // lineups. Interestingly, in these situations, the value returned
        // for each team when following the Nash equilibrium (minimax)
        // strategy may not be the same. Instead, as stated earlier, each
        // team will get the best value they can be guaranteed to get
        // without leaving themselves open to counter exploitation. Its
        // impossible for these values to contradict each other.

        if (root_selecting_team == A) {
            // find the best (max) value A can get with a lineup where
            // each value is the best (min) value B can get in response
            int value_max = -INF;

            for (int i = 0; i < num_teams; i++) {
                int value_min = INF;

                for (int j = 0; j < num_e_teams; j++) {
                    int value = rr_values[i] + e_rr_values[j] + terminal_value(teams[i], e_teams[j]);

                    if (value < value_min)
                        value_min = value;

                    if (value_min <= value_max)
                        // team A won't use this lineup
                        break;
                }

                if (value_min > value_max)
                    value_max = value_min;
            }

            return value_max;
        } else {
            // find the best (min) value B can get with a lineup where
            // each value is the best (max) value A can get in response
            int value_min = INF;

            for (int i = 0; i < num_e_teams; i++) {
                int value_max = -INF;

                for (int j = 0; j < num_teams; j++) {
                    int value = rr_values[j] + e_rr_values[i] + terminal_value(teams[j], e_teams[i]);

                    if (value > value_max)
                        value_max = value;

                    if (value_max >= value_min)
                        // team B won't use this lineup
                        break;
                }

                if (value_max < value_min)
                    value_min = value_max;
            }

            return value_min;
        }
    }

    // if there are multiple enemy lineups and its not a terminal 
    // state, then each legal hero is searched to get state value
    int value = -INF;
    switch (draft[stage].selection) {
        case PICK:
            for (int h = 0; h < num_heroes; h++) {
                u64 teams_p[num_teams];
                u64 legals_p[num_teams];
                int rr_values_p[num_teams];
                u64 hashes_p[num_teams];
                int num_teams_p = hero_in_team_update(
                    h,
                    draft[stage].team,
                    num_teams,
                    teams,
                    legals,
                    rr_values,
                    hashes,
                    teams_p,
                    legals_p,
                    rr_values_p,
                    hashes_p
                );

                // skip hero if not legal for any team lineup
                if (num_teams_p == 0)
                    continue;

                // must update all enemy legals as well if continuing
                u64 e_legals_p[num_e_teams];
                hero_out_of_team_update(h, num_e_teams, e_legals, e_legals_p);

                int child_value = -flex_negamax(
                    num_e_teams,
                    num_teams_p,
                    e_teams,
                    teams_p,
                    e_legals_p,
                    legals_p,
                    e_rr_values,
                    rr_values_p,
                    e_hashes,
                    hashes_p,
                    bans_hash,
                    stage + 1,
                    -beta,
                    -alpha
                );

                if (child_value > value)
                    value = child_value;

                if (value > alpha)
                    alpha = value;

                if (alpha >= beta)
                    return value;
            }
            break;

        case BAN:
            for (int h = 0; h < num_heroes; h++) {
                // if hero is legal for at least one enemy lineup then
                // the response values of all enemy lineups must be
                // considered (not only those where it is legal) as its
                // possible the enemy could do better using a lineup
                // where the hero is illegal
                if (!legal_for_any_lineup(h, num_e_teams, e_legals))
                    continue;

                // get updated legals for both teams after the ban
                u64 legals_b[num_teams];
                hero_out_of_team_update(h, num_teams, legals, legals_b);
                u64 e_legals_b[num_e_teams];
                hero_out_of_team_update(h, num_e_teams, e_legals, e_legals_b);

                int child_value = -flex_negamax(
                    num_e_teams,
                    num_teams,
                    e_teams,
                    teams,
                    e_legals_b,
                    legals_b,
                    e_rr_values,
                    rr_values,
                    e_hashes,
                    hashes,
                    bans_hash ^ zobrist_keys[BAN_KEYS][h],
                    stage + 1,
                    -beta,
                    -alpha
                );

                if (child_value > value)
                    value = child_value;

                if (value > alpha)
                    alpha = value;

                if (alpha >= beta)
                    return value;
            }
            break;

        case PICK_PICK:
            for (int h = 0; h < num_heroes; h++) {
                // update lineups for first pick
                u64 teams_p[num_teams];
                u64 legals_p[num_teams];
                int rr_values_p[num_teams];
                u64 hashes_p[num_teams];
                int num_teams_p = hero_in_team_update(
                    h,
                    draft[stage].team,
                    num_teams,
                    teams,
                    legals,
                    rr_values,
                    hashes,
                    teams_p,
                    legals_p,
                    rr_values_p,
                    hashes_p
                );

                if (num_teams_p == 0)
                    continue;

                u64 e_legals_p[num_e_teams];
                hero_out_of_team_update(h, num_e_teams, e_legals, e_legals_p);

                for (int h2 = h + 1; h2 < num_heroes; h2++) {
                    // update lineups for second pick
                    u64 teams_pp[num_teams_p];
                    u64 legals_pp[num_teams_p];
                    int rr_values_pp[num_teams_p];
                    u64 hashes_pp[num_teams_p];
                    int num_teams_pp = hero_in_team_update(
                        h2,
                        draft[stage].team,
                        num_teams_p,
                        teams_p,
                        legals_p,
                        rr_values_p,
                        hashes_p,
                        teams_pp,
                        legals_pp,
                        rr_values_pp,
                        hashes_pp
                    );

                    if (num_teams_pp == 0)
                        continue;

                    u64 e_legals_pp[num_e_teams];
                    hero_out_of_team_update(h2, num_e_teams, e_legals_p, e_legals_pp);

                    int child_value = -flex_negamax(
                        num_e_teams,
                        num_teams_pp,
                        e_teams,
                        teams_pp,
                        e_legals_pp,
                        legals_pp,
                        e_rr_values,
                        rr_values_pp,
                        e_hashes,
                        hashes_pp,
                        bans_hash,
                        stage + 2,
                        -beta,
                        -alpha
                    );

                    if (child_value > value)
                        value = child_value;

                    if (value > alpha)
                        alpha = value;

                    if (alpha >= beta)
                        return value;
                }
            }
            break;

        case PICK_BAN:
            for (int h = 0; h < num_heroes; h++) {
                // update lineups for pick
                u64 teams_p[num_teams];
                u64 legals_p[num_teams];
                int rr_values_p[num_teams];
                u64 hashes_p[num_teams];
                int num_teams_p = hero_in_team_update(
                    h,
                    draft[stage].team,
                    num_teams,
                    teams,
                    legals,
                    rr_values,
                    hashes,
                    teams_p,
                    legals_p,
                    rr_values_p,
                    hashes_p
                );

                if (num_teams_p == 0)
                    continue;

                u64 e_legals_p[num_e_teams];
                hero_out_of_team_update(h, num_e_teams, e_legals, e_legals_p);

                for (int h2 = 0; h2 < num_heroes; h2++) {
                    if (!legal_for_any_lineup(h2, num_e_teams, e_legals_p))
                        continue;

                    // update lineups for ban
                    u64 legals_pb[num_teams_p];
                    hero_out_of_team_update(h2, num_teams_p, legals_p, legals_pb);
                    u64 e_legals_pb[num_e_teams];
                    hero_out_of_team_update(h2, num_e_teams, e_legals_p, e_legals_pb);

                    int child_value = -flex_negamax(
                        num_e_teams,
                        num_teams_p,
                        e_teams,
                        teams_p,
                        e_legals_pb,
                        legals_pb,
                        e_rr_values,
                        rr_values_p,
                        e_hashes,
                        hashes_p,
                        bans_hash ^ zobrist_keys[BAN_KEYS][h2],
                        stage + 2,
                        -beta,
                        -alpha
                    );

                    if (child_value > value)
                        value = child_value;

                    if (value > alpha)
                        alpha = value;

                    if (alpha >= beta)
                        return value;
                }
            }
            break;

        case BAN_PICK:
            for (int h = 0; h < num_heroes; h++) {
                if (!legal_for_any_lineup(h, num_e_teams, e_legals))
                    continue;

                // update lineups for ban
                u64 legals_b[num_teams];
                hero_out_of_team_update(h, num_teams, legals, legals_b);
                u64 e_legals_b[num_e_teams];
                hero_out_of_team_update(h, num_e_teams, e_legals, e_legals_b);
                u64 bans_hash_b = bans_hash ^ zobrist_keys[BAN_KEYS][h];

                for (int h2 = 0; h2 < num_heroes; h2++) {
                    // update lineups for pick
                    u64 teams_bp[num_teams];
                    u64 legals_bp[num_teams];
                    int rr_values_bp[num_teams];
                    u64 hashes_bp[num_teams];
                    int num_teams_bp = hero_in_team_update(
                        h2,
                        draft[stage].team,
                        num_teams,
                        teams,
                        legals_b,
                        rr_values,
                        hashes,
                        teams_bp,
                        legals_bp,
                        rr_values_bp,
                        hashes_bp
                    );

                    if (num_teams_bp == 0)
                        continue;

                    u64 e_legals_bp[num_e_teams];
                    hero_out_of_team_update(h2, num_e_teams, e_legals_b, e_legals_bp);

                    int child_value = -flex_negamax(
                        num_e_teams,
                        num_teams_bp,
                        e_teams,
                        teams_bp,
                        e_legals_bp,
                        legals_bp,
                        e_rr_values,
                        rr_values_bp,
                        e_hashes,
                        hashes_bp,
                        bans_hash_b,
                        stage + 2,
                        -beta,
                        -alpha
                    );

                    if (child_value > value)
                        value = child_value;

                    if (value > alpha)
                        alpha = value;

                    if (alpha >= beta)
                        return value;
                }
            }
            break;

        case BAN_BAN:
            for (int h = 0; h < num_heroes; h++) {
                if (!legal_for_any_lineup(h, num_e_teams, e_legals))
                    continue;

                // update lineups for first ban
                u64 legals_b[num_teams];
                hero_out_of_team_update(h, num_teams, legals, legals_b);
                u64 e_legals_b[num_e_teams];
                hero_out_of_team_update(h, num_e_teams, e_legals, e_legals_b);
                u64 bans_hash_b = bans_hash ^ zobrist_keys[BAN_KEYS][h];

                for (int h2 = h + 1; h2 < num_heroes; h2++) {
                    if (!legal_for_any_lineup(h2, num_e_teams, e_legals_b))
                        continue;

                    // update lineups for second ban
                    u64 legals_bb[num_teams];
                    hero_out_of_team_update(h2, num_teams, legals_b, legals_bb);
                    u64 e_legals_bb[num_e_teams];
                    hero_out_of_team_update(h2, num_e_teams, e_legals_b, e_legals_bb);

                    int child_value = -flex_negamax(
                        num_e_teams,
                        num_teams,
                        e_teams,
                        teams,
                        e_legals_bb,
                        legals_bb,
                        e_rr_values,
                        rr_values,
                        e_hashes,
                        hashes,
                        bans_hash_b ^ zobrist_keys[BAN_KEYS][h2],
                        stage + 2,
                        -beta,
                        -alpha
                    );

                    if (child_value > value)
                        value = child_value;

                    if (value > alpha)
                        alpha = value;

                    if (alpha >= beta)
                        return value;
                }
            }
            break;
    }

    return value;
}


//
// Initialise an array of hero nums from a team bit string.
// Returns pointer to the next position needing filled.
//
int *init_team_heroes(u64 team, int *team_ptr)
{
    for (int h = 0; h < num_heroes; h++) {
        if (team & (1ULL << h)) {
            *team_ptr = h;
            team_ptr += 1;
        }
    }

    return team_ptr;
}


// 
// Updates all team lineups, legal actions and hash of picks where it's
// possible to select the given hero, returning how many new lineups
// there are.
//
int hero_in_team_update(
    int hero_num,
    enum team selecting_team,
    int num_teams,
    u64 teams[],
    u64 legals[],
    int rr_values[],
    u64 hashes[],
    u64 new_teams[],
    u64 new_legals[],
    int new_rr_values[],
    u64 new_hashes[]
)
{
    int new_num_teams = 0;
    u64 hero = 1ULL << hero_num;

    for (int i = 0; i < num_teams; i++) {
        if (legals[i] & hero) {
            // only update state for a lineup where hero is legal
            new_teams[new_num_teams] = teams[i] | hero;
            new_legals[new_num_teams] = legals[i] & h_infos[hero_num].diff_role_and_h;
            new_rr_values[new_num_teams] = rr_values[i] + (selecting_team == A ? role_rs[hero_num].A_value :
                                                                                 -role_rs[hero_num].B_value);
            new_hashes[new_num_teams] = hashes[i] ^ zobrist_keys[selecting_team][hero_num];
            new_num_teams += 1;
        }
    }

    return new_num_teams;
}


// 
// Updates the legal actions for all lineups of a team when a hero is
// either banned or selected by the enemy.
//
void hero_out_of_team_update(int hero_num, int num_teams, u64 legals[], u64 new_legals[])
{
    for (int i = 0; i < num_teams; i++) {
        new_legals[i] = legals[i] & h_infos[hero_num].diff_h;
    }
}


//
// Checks if a given hero is legal in any of a team's
// starting lineup legal actions.
//
int legal_for_any_lineup(int hero_num, int num_teams, u64 legals[])
{
    u64 hero = 1ULL << hero_num;

    for (int i = 0; i < num_teams; i++) {
        if (legals[i] & hero)
            return 1;
    }

    return 0;
}


//
// Similar to flex_negamax, modified to track and return the optimal
// action(s) alongside the value. This is only needed at the root and
// would be wasteful to both track and return at every depth.
//
// Additionally, multiple branches are evaluated in parallel with each
// thread taking the next unevaluated hero when they are done. This
// simple approach has many benefits. Firstly, the ordering of heroes is
// fixed based off of potential which may not be perfect in all states,
// so having the first group of heroes initially run together provides a
// higher chance of finding the best value for later cutoffs. Secondly,
// sequentially evaluating all heroes can be done faster. Thirdly, in
// combination with the transposition table, all threads can share
// state evaluations which can reduce the time to evaluate a single hero.
//
struct search_result root_negamax(
    int num_teams,
    int num_e_teams,
    u64 teams[],
    u64 e_teams[],
    u64 legals[],
    u64 e_legals[],
    int rr_values[],
    int e_rr_values[],
    u64 hashes[],
    u64 e_hashes[],
    u64 bans_hash,
    int stage
)
{
    struct search_result ret = {.value = -INF};
    switch (draft[stage].selection) {
        case PICK:
            #pragma omp parallel for schedule(dynamic, 1)
            for (int h = 0; h < num_heroes; h++) {
                u64 teams_p[num_teams];
                u64 legals_p[num_teams];
                int rr_values_p[num_teams];
                u64 hashes_p[num_teams];
                int num_teams_p = hero_in_team_update(
                    h,
                    draft[stage].team,
                    num_teams,
                    teams,
                    legals,
                    rr_values,
                    hashes,
                    teams_p,
                    legals_p,
                    rr_values_p,
                    hashes_p
                );

                // skip hero if not legal for any team lineup
                if (num_teams_p == 0)
                    continue;

                // must update all enemy legals as well if continuing
                u64 e_legals_p[num_e_teams];
                hero_out_of_team_update(h, num_e_teams, e_legals, e_legals_p);

                int child_value = -flex_negamax(
                    num_e_teams,
                    num_teams_p,
                    e_teams,
                    teams_p,
                    e_legals_p,
                    legals_p,
                    e_rr_values,
                    rr_values_p,
                    e_hashes,
                    hashes_p,
                    bans_hash,
                    stage + 1,
                    -INF,
                    -ret.value    // use current best value
                );

                #pragma omp critical
                {
                    if (child_value > ret.value) {
                        ret.value = child_value;
                        ret.best_hero = h;
                    }
                }
            }
            return ret;

        case BAN:
            #pragma omp parallel for schedule(dynamic, 1)
            for (int h = 0; h < num_heroes; h++) {
                // if hero is legal for at least one enemy lineup then
                // the response values of all enemy lineups must be
                // considered (not only those where it is legal) as its
                // possible the enemy could do better using a lineup
                // where the hero is illegal
                if (!legal_for_any_lineup(h, num_e_teams, e_legals))
                    continue;

                // get updated legals for both teams after the ban
                u64 legals_b[num_teams];
                hero_out_of_team_update(h, num_teams, legals, legals_b);
                u64 e_legals_b[num_e_teams];
                hero_out_of_team_update(h, num_e_teams, e_legals, e_legals_b);

                int child_value = -flex_negamax(
                    num_e_teams,
                    num_teams,
                    e_teams,
                    teams,
                    e_legals_b,
                    legals_b,
                    e_rr_values,
                    rr_values,
                    e_hashes,
                    hashes,
                    bans_hash ^ zobrist_keys[BAN_KEYS][h],
                    stage + 1,
                    -INF,
                    -ret.value
                );

                #pragma omp critical
                {
                    if (child_value > ret.value) {
                        ret.value = child_value;
                        ret.best_hero = h;
                    }
                }
            }
            return ret;

        case PICK_PICK:
            #pragma omp parallel for schedule(dynamic, 1)
            for (int h = 0; h < num_heroes; h++) {
                // update lineups for first pick
                u64 teams_p[num_teams];
                u64 legals_p[num_teams];
                int rr_values_p[num_teams];
                u64 hashes_p[num_teams];
                int num_teams_p = hero_in_team_update(
                    h,
                    draft[stage].team,
                    num_teams,
                    teams,
                    legals,
                    rr_values,
                    hashes,
                    teams_p,
                    legals_p,
                    rr_values_p,
                    hashes_p
                );

                if (num_teams_p == 0)
                    continue;

                u64 e_legals_p[num_e_teams];
                hero_out_of_team_update(h, num_e_teams, e_legals, e_legals_p);

                for (int h2 = h + 1; h2 < num_heroes; h2++) {
                    // update lineups for second pick
                    u64 teams_pp[num_teams_p];
                    u64 legals_pp[num_teams_p];
                    int rr_values_pp[num_teams_p];
                    u64 hashes_pp[num_teams_p];
                    int num_teams_pp = hero_in_team_update(
                        h2,
                        draft[stage].team,
                        num_teams_p,
                        teams_p,
                        legals_p,
                        rr_values_p,
                        hashes_p,
                        teams_pp,
                        legals_pp,
                        rr_values_pp,
                        hashes_pp
                    );

                    if (num_teams_pp == 0)
                        continue;

                    u64 e_legals_pp[num_e_teams];
                    hero_out_of_team_update(h2, num_e_teams, e_legals_p, e_legals_pp);

                    int child_value = -flex_negamax(
                        num_e_teams,
                        num_teams_pp,
                        e_teams,
                        teams_pp,
                        e_legals_pp,
                        legals_pp,
                        e_rr_values,
                        rr_values_pp,
                        e_hashes,
                        hashes_pp,
                        bans_hash,
                        stage + 2,
                        -INF,
                        -ret.value
                    );

                    #pragma omp critical
                    {
                        if (child_value > ret.value) {
                            ret.value = child_value;
                            ret.best_hero = h;
                            ret.best_hero_2 = h2;
                        }
                    }
                }
            }
            return ret;

        case PICK_BAN:
            #pragma omp parallel for schedule(dynamic, 1)
            for (int h = 0; h < num_heroes; h++) {
                // update lineups for pick
                u64 teams_p[num_teams];
                u64 legals_p[num_teams];
                int rr_values_p[num_teams];
                u64 hashes_p[num_teams];
                int num_teams_p = hero_in_team_update(
                    h,
                    draft[stage].team,
                    num_teams,
                    teams,
                    legals,
                    rr_values,
                    hashes,
                    teams_p,
                    legals_p,
                    rr_values_p,
                    hashes_p
                );

                if (num_teams_p == 0)
                    continue;

                u64 e_legals_p[num_e_teams];
                hero_out_of_team_update(h, num_e_teams, e_legals, e_legals_p);

                for (int h2 = 0; h2 < num_heroes; h2++) {
                    if (!legal_for_any_lineup(h2, num_e_teams, e_legals_p))
                        continue;

                    // update lineups for ban
                    u64 legals_pb[num_teams_p];
                    hero_out_of_team_update(h2, num_teams_p, legals_p, legals_pb);
                    u64 e_legals_pb[num_e_teams];
                    hero_out_of_team_update(h2, num_e_teams, e_legals_p, e_legals_pb);

                    int child_value = -flex_negamax(
                        num_e_teams,
                        num_teams_p,
                        e_teams,
                        teams_p,
                        e_legals_pb,
                        legals_pb,
                        e_rr_values,
                        rr_values_p,
                        e_hashes,
                        hashes_p,
                        bans_hash ^ zobrist_keys[BAN_KEYS][h2],
                        stage + 2,
                        -INF,
                        -ret.value
                    );

                    #pragma omp critical
                    {
                        if (child_value > ret.value) {
                            ret.value = child_value;
                            ret.best_hero = h;
                            ret.best_hero_2 = h2;
                        }
                    }
                }
            }
            return ret;

        case BAN_PICK:
            #pragma omp parallel for schedule(dynamic, 1)
            for (int h = 0; h < num_heroes; h++) {
                if (!legal_for_any_lineup(h, num_e_teams, e_legals))
                    continue;

                // update lineups for ban
                u64 legals_b[num_teams];
                hero_out_of_team_update(h, num_teams, legals, legals_b);
                u64 e_legals_b[num_e_teams];
                hero_out_of_team_update(h, num_e_teams, e_legals, e_legals_b);
                u64 bans_hash_b = bans_hash ^ zobrist_keys[BAN_KEYS][h];

                for (int h2 = 0; h2 < num_heroes; h2++) {
                    // update lineups for pick
                    u64 teams_bp[num_teams];
                    u64 legals_bp[num_teams];
                    int rr_values_bp[num_teams];
                    u64 hashes_bp[num_teams];
                    int num_teams_bp = hero_in_team_update(
                        h2,
                        draft[stage].team,
                        num_teams,
                        teams,
                        legals_b,
                        rr_values,
                        hashes,
                        teams_bp,
                        legals_bp,
                        rr_values_bp,
                        hashes_bp
                    );

                    if (num_teams_bp == 0)
                        continue;

                    u64 e_legals_bp[num_e_teams];
                    hero_out_of_team_update(h2, num_e_teams, e_legals_b, e_legals_bp);

                    int child_value = -flex_negamax(
                        num_e_teams,
                        num_teams_bp,
                        e_teams,
                        teams_bp,
                        e_legals_bp,
                        legals_bp,
                        e_rr_values,
                        rr_values_bp,
                        e_hashes,
                        hashes_bp,
                        bans_hash_b,
                        stage + 2,
                        -INF,
                        -ret.value
                    );

                    #pragma omp critical
                    {
                        if (child_value > ret.value) {
                            ret.value = child_value;
                            ret.best_hero = h;
                            ret.best_hero_2 = h2;
                        }
                    }
                }
            }
            return ret;

        case BAN_BAN:
            #pragma omp parallel for schedule(dynamic, 1)
            for (int h = 0; h < num_heroes; h++) {
                if (!legal_for_any_lineup(h, num_e_teams, e_legals))
                    continue;

                // update lineups for first ban
                u64 legals_b[num_teams];
                hero_out_of_team_update(h, num_teams, legals, legals_b);
                u64 e_legals_b[num_e_teams];
                hero_out_of_team_update(h, num_e_teams, e_legals, e_legals_b);
                u64 bans_hash_b = bans_hash ^ zobrist_keys[BAN_KEYS][h];

                for (int h2 = h + 1; h2 < num_heroes; h2++) {
                    if (!legal_for_any_lineup(h2, num_e_teams, e_legals_b))
                        continue;

                    // update lineups for second ban
                    u64 legals_bb[num_teams];
                    hero_out_of_team_update(h2, num_teams, legals_b, legals_bb);
                    u64 e_legals_bb[num_e_teams];
                    hero_out_of_team_update(h2, num_e_teams, e_legals_b, e_legals_bb);

                    int child_value = -flex_negamax(
                        num_e_teams,
                        num_teams,
                        e_teams,
                        teams,
                        e_legals_bb,
                        legals_bb,
                        e_rr_values,
                        rr_values,
                        e_hashes,
                        hashes,
                        bans_hash_b ^ zobrist_keys[BAN_KEYS][h2],
                        stage + 2,
                        -INF,
                        -ret.value
                    );

                    #pragma omp critical
                    {
                        if (child_value > ret.value) {
                            ret.value = child_value;
                            ret.best_hero = h;
                            ret.best_hero_2 = h2;
                        }
                    }
                }
            }
            return ret;
    }
}


// 
// Outer search function. Takes in any starting state of selected
// hero nums (that includes all role variations), sets up initial
// bit format variables, then calls root_negamax for the selecting
// team to return optimal value and action(s).
//
struct search_result run_search(
    int num_teams_A,
    int num_teams_B,
    int team_A_size,
    int team_B_size,
    int banned_size,
    int** start_teams_A,
    int** start_teams_B,
    int* banned
)
{
    // init team A teams, legals, rr_values and starting hashes for all lineups
    u64 teams_A[num_teams_A];
    u64 legals_A[num_teams_A];
    int rr_values_A[num_teams_A];
    u64 hashes_A[num_teams_A];
    for (int i = 0; i < num_teams_A; i++) {
        teams_A[i] = team_bit_repr(team_A_size, start_teams_A[i]);
        legals_A[i] = legal_bit_repr(
            team_A_size,
            team_B_size,
            banned_size,
            start_teams_A[i],
            start_teams_B[0],  // any enemy team can be used as all hero variations are removed
            banned
        );
        rr_values_A[i] = init_rr_value(A, team_A_size, start_teams_A[i]);
        hashes_A[i] = init_hash(A, team_A_size, start_teams_A[i]);
    }

    // init team B teams, legals, rr_values and starting hashes for all lineups
    u64 teams_B[num_teams_B];
    u64 legals_B[num_teams_B];
    int rr_values_B[num_teams_B];
    u64 hashes_B[num_teams_B];
    for (int i = 0; i < num_teams_B; i++) {
        teams_B[i] = team_bit_repr(team_B_size, start_teams_B[i]);
        legals_B[i] = legal_bit_repr(
            team_B_size,
            team_A_size,
            banned_size,
            start_teams_B[i],
            start_teams_A[0],
            banned
        );
        rr_values_B[i] = init_rr_value(B, team_B_size, start_teams_B[i]);
        hashes_B[i] = init_hash(B, team_B_size, start_teams_B[i]);
    }

    // init hash of all bans (only single hash needed as a ban
    // from either team of any role variation is equivalent)
    u64 bans_hash = init_hash(BAN_KEYS, banned_size, banned);

    // call search for selecting team
    int stage = team_A_size + team_B_size + banned_size;
    root_selecting_team = draft[stage].team;
    if (draft[stage].team == A)
        return root_negamax(
            num_teams_A,
            num_teams_B,
            teams_A,
            teams_B,
            legals_A,
            legals_B,
            rr_values_A,
            rr_values_B,
            hashes_A,
            hashes_B,
            bans_hash,
            stage
        );
     else
        return root_negamax(
            num_teams_B,
            num_teams_A,
            teams_B,
            teams_A,
            legals_B,
            legals_A,
            rr_values_B,
            rr_values_A,
            hashes_B,
            hashes_A,
            bans_hash,
            stage
        );
}


// 
// Turn array of hero nums into their bit representation.
//
u64 team_bit_repr(int team_size, int team_nums[])
{
    u64 team = 0;  // start with empty team

    for (int i = 0; i < team_size; i++) {
        team |= (1ULL << team_nums[i]);
    }

    return team;
}


// 
// Get the legal actions for a team in bit representation given 
// arrays of hero nums for team, enemy and bans.
//
u64 legal_bit_repr(
    int team_size,
    int e_team_size,
    int banned_size,
    int team_nums[],
    int e_team_nums[],
    int banned_nums[]
)
{
    u64 legal = 0xFFFFFFFFFFFFFFFF;  // init all heroes as legal

    // remove team heroes (and their shared roles and flex nums)
    for (int i = 0; i < team_size; i++) {
        legal &= h_infos[team_nums[i]].diff_role_and_h;
    }

    // remove selected enemy heroes (including flex nums)
    for (int i = 0; i < e_team_size; i++) {
        legal &= h_infos[e_team_nums[i]].diff_h;
    }

    // remove banned heroes (including flex nums)
    for (int i = 0; i < banned_size; i++) {
        legal &= h_infos[banned_nums[i]].diff_h;
    }

    return legal;
}


//
// XOR the zobrist keys for each hero in a set of team picks
// or all bans.
//
u64 init_hash(int team_or_ban, int hero_nums_size, int hero_nums[])
{
    u64 hash = 0ULL;

    for (int i = 0; i < hero_nums_size; i++) {
        hash ^= zobrist_keys[team_or_ban][hero_nums[i]];
    }

    return hash;
}


//
// Initialise the running role reward value (in terms of team
// A's perspective) for the given team.
//
int init_rr_value(int team, int hero_nums_size, int hero_nums[])
{
    int value = 0;

    if (team == A) {
        for (int i = 0; i < hero_nums_size; i++) {
            value += role_rs[hero_nums[i]].A_value;
        }
    } else {
        for (int i = 0; i < hero_nums_size; i++) {
            value -= role_rs[hero_nums[i]].B_value;
        }
    }

    return value;
}


// ======================================================================
// I need a way to go from receiving a draft format and set of rewards in
// python to initialising the global variables required for calling
// searches. For now having python do most of the processing and 
// initialising individual elements seems easiest. However, I may want to 
// change this @Later. The following are used in the __init__ of the
// python DraftAI wrapper class.

void set_role_r(int hero_num, int A_value, int B_value)
{
    role_rs[hero_num].A_value = A_value;
    role_rs[hero_num].B_value = B_value;
}


void set_synergy_r(int i, int heroes_size, int hero_nums[], int A_value, int B_value)
{
    synergy_rs[i].heroes = team_bit_repr(heroes_size, hero_nums);
    synergy_rs[i].A_value = A_value;
    synergy_rs[i].B_value = B_value;
}


void set_counter_r(int i, int heroes_size, int hero_nums[], int foes_size, 
                   int foe_nums[], int A_value, int B_value)
{
    counter_rs[i].heroes = team_bit_repr(heroes_size, hero_nums);
    counter_rs[i].foes = team_bit_repr(foes_size, foe_nums);
    counter_rs[i].A_value = A_value;
    counter_rs[i].B_value = B_value;
}


void set_draft_stage(int stage, int team, int selection)
{
    draft[stage].team = team;
    draft[stage].selection = selection;
}


void set_h_info(int hero_num, int same_role_and_h_size, int same_role_and_h_nums[],
                int same_h_size, int same_h_nums[])
{
    h_infos[hero_num].diff_role_and_h = ~team_bit_repr(same_role_and_h_size,
                                                       same_role_and_h_nums);
    h_infos[hero_num].diff_h = ~team_bit_repr(same_h_size, same_h_nums);
}


void set_sizes(int heroes, int synergy_rs, int counter_rs, int draft)
{
    num_heroes = heroes;
    num_synergy_rs = synergy_rs;
    num_counter_rs = counter_rs;
    draft_len = draft;
}

void set_zobrist_key(int team_or_ban, int hero_num, u64 key)
{
    zobrist_keys[team_or_ban][hero_num] = key;
}

// ======================================================================


//
// Clear transposition table to run search with new reward values.
//
void clear_tt()
{
    for (u64 i = 0; i < TT_IDX_BITS + 1; i++) {
        tt[i].tag = 0;
    }
}

//
// Save the transposition table, and the zobrist keys used to access it,
// to the given file for later reuse.
//
int write_tt_and_zobrist_keys(const char *filename)
{
    int num_keys = 3 * MAX_NUM_HEROES;
    int num_tt_entries = TT_IDX_BITS + 1;
    FILE *f = fopen(filename, "wb");
    int keys_w = fwrite(zobrist_keys, sizeof(u64), num_keys, f);
    int tt_entries_w = fwrite(tt, sizeof(struct tt_entry), num_tt_entries, f);
    fclose(f);
    return keys_w == num_keys && tt_entries_w == num_tt_entries;
}

// 
// Load a previously saved transposition table, and the zobrist keys used
// to access it, from the given file, ready to be used for running search.
//
int read_tt_and_zobrist_keys(const char *filename)
{
    int num_keys = 3 * MAX_NUM_HEROES;
    int num_tt_entries = TT_IDX_BITS + 1;
    FILE *f = fopen(filename, "rb");
    int keys_r = fread(zobrist_keys, sizeof(u64), num_keys, f);
    int tt_entries_r = fread(tt, sizeof(struct tt_entry), num_tt_entries, f);
    fclose(f);
    return keys_r == num_keys && tt_entries_r == num_tt_entries;
}

//
// Gets all constants defined in draft_ai.h to ensure that the python
// files preparing inputs can stay consistent.
//
struct constants_s get_constants()
{
    struct constants_s constants;

    // max sizes
    constants.max_num_heroes = MAX_NUM_HEROES;
    constants.max_synergy_rs = MAX_SYNERGY_RS;
    constants.max_counter_rs = MAX_COUNTER_RS;
    constants.max_draft_len = MAX_DRAFT_LEN;

    // teams / zobrist table indices
    constants.a = A;
    constants.b = B;
    constants.ban_keys = BAN_KEYS;

    // selection types
    constants.pick = PICK;
    constants.ban = BAN;
    constants.pick_pick = PICK_PICK;
    constants.pick_ban = PICK_BAN;
    constants.ban_pick = BAN_PICK;
    constants.ban_ban = BAN_BAN;

    constants.inf = INF;

    constants.max_tt_stage = MAX_TT_STAGE;

    return constants;
}
