#include "draft_ai.h"

// sizes
int num_heroes;
int num_synergy_rs;
int num_counter_rs;
int draft_len;

// rewards
struct role_r role_rs[MAX_NUM_HEROES];
struct synergy_r synergy_rs[MAX_SYNERGIES];
struct counter_r counter_rs[MAX_COUNTERS];

// info needed to update legal actions
struct h_info h_infos[MAX_NUM_HEROES];

// team selecting and selection type for each stage in draft
struct draft_stage draft[MAX_DRAFT_LEN]; 


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
int negamax(u64 team, u64 e_team, u64 legal, u64 e_legal, int stage, int alpha, int beta)
{
    if (stage == draft_len)
        // since B has last pick in draft it is always
        // guaranteed that team is A and e_team is B
        return terminal_value(team, e_team);

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
                    stage + 1,
                    -beta,
                    -alpha
                );

                if (child_value >= value)
                    value = child_value;

                if (value >= alpha)
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
                    stage + 1,
                    -beta,
                    -alpha
                );

                if (child_value >= value)
                    value = child_value;

                if (value >= alpha)
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
                        stage + 2,
                        -beta,
                        -alpha
                    );

                    if (child_value >= value)
                        value = child_value;

                    if (value >= alpha)
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
                        stage + 2,
                        -beta,
                        -alpha
                    );

                    if (child_value >= value)
                        value = child_value;

                    if (value >= alpha)
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
                        stage + 2,
                        -beta,
                        -alpha
                    );

                    if (child_value >= value)
                        value = child_value;

                    if (value >= alpha)
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

                // order for double bans is irrelevant
                for (int h2 = h + 1; h2 < num_heroes; h2++) {
                    if (!(new_e_legal & (1ULL << h2)))
                        continue;

                    int child_value = -negamax(
                        e_team,
                        team,
                        new_e_legal & h_infos[h2].diff_h,
                        new_legal & h_infos[h2].diff_h,
                        stage + 2,
                        -beta,
                        -alpha
                    );

                    if (child_value >= value)
                        value = child_value;

                    if (value >= alpha)
                        alpha = value;

                    if (alpha >= beta)
                        goto cutoff;

                }
            }
            break;
    }

cutoff:
    return value;
}


// 
// Evaluate rewards from team A's perspective. 
//
// @Later I may want to try tracking hero nums for each team
// in array of 5 for quicker evaluation of role rewards.
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

    // role rewards 
    u64 hero = 1ULL;  // represents hero 0 (first bit)
    for (int i = 0; i < num_heroes; i++) {
        if (team_A & hero)
            value += role_rs[i].A_value;
        else if (team_B & hero)
            value -= role_rs[i].B_value;
        hero <<= 1;
    }

    return value;
}


//
// ** Will be deleted when run_main_search is complete. **
//
// Outer search function that takes in any combination of 
// picks and bans, sets up initial bit format variables,
// then calls negamax for the selecting team.
//
// Assumes that teams/bans that are not full terminate with
// a -1.
// 
int run_search(int team_A_nums[], int team_B_nums[], int banned_nums[])
{
    u64 team_A = 0;                         // init teams as being empty
    u64 team_B = 0;
    u64 team_A_legal = 0xFFFFFFFFFFFFFFFF;  // init all heroes as legal
    u64 team_B_legal = 0xFFFFFFFFFFFFFFFF;
    int stage = 0;

    // remove banned heroes (including flex nums) from legals
    for (int i = 0; i < MAX_DRAFT_LEN - 10; i++) {
        int hero_num = banned_nums[i];
        if (hero_num == -1)
            break;

        team_A_legal &= h_infos[hero_num].diff_h;
        team_B_legal &= h_infos[hero_num].diff_h;

        stage += 1;
    }

    // team A picks
    for (int i = 0; i < 5; i++) {
        int hero_num = team_A_nums[i];
        if (hero_num == -1)
            break;

        team_A |= (1ULL << hero_num);

        team_A_legal &= h_infos[hero_num].diff_role_and_h;
        team_B_legal &= h_infos[hero_num].diff_h;

        stage += 1;
    }

    // team B picks
    for (int i = 0; i < 5; i++) {
        int hero_num = team_B_nums[i];
        if (hero_num == -1)
            break;

        team_B |= (1ULL << hero_num);

        team_B_legal &= h_infos[hero_num].diff_role_and_h;
        team_A_legal &= h_infos[hero_num].diff_h;

        stage += 1;
    }

    // run negamax with initial state
    int value;
    if (draft[stage].team == A) {
        value = negamax(
            team_A,
            team_B,
            team_A_legal,
            team_B_legal,
            stage,
            -INF,
            INF
        );
    } else {
        value = negamax(
            team_B,
            team_A,
            team_B_legal,
            team_A_legal,
            stage,
            -INF,
            INF
        );
    }

    // after implementing the TT I would retrieve the best action(s)
    // from it at this point using the zobrist hash created at start
    return value;
}


// 
// Outer search function. Takes in any history of hero num lineups for
// both teams and bans, initialises bit format variables, then calls
// the appropriate root selection search to return optimal value and 
// action(s).
//
// The root functions are similar to their selection counterpart in
// negamax. However, they also track the optimal action and deal with
// the fact that teams could have many starting lineups. There may be
// many because heroes who play multiple roles are treated differently.
// If hero X plays two roles and X is selected in a real draft, we must
// consider X being played in either role. The value of selecting a hero
// (or two) is therefore the minimum value returned for each enemy team
// starting lineup used, which in turn is the maximum value of using each
// selecting team lineup vs it. The enemy gets preference on which lineup
// to use as it is them to select after the hero being evaluated is 
// selected--their action will be based on the lineup that gets them most
// value.
//
struct search_result run_main_search(
    int num_teams,
    int num_e_teams,
    int team_size,
    int e_team_size,
    int banned_size,
    int** start_teams,
    int** start_e_teams,
    int* banned
)
{
    // starting state variables for all hero role assignments
    u64 teams[num_teams];
    u64 e_teams[num_e_teams];
    u64 legals[num_teams];
    u64 e_legals[num_e_teams];

    // init starting team variables
    for (int i = 0; i < num_teams; i++) {
        teams[i] = team_bit_repr(team_size, start_teams[i]);
        legals[i] = legal_bit_repr(
            team_size,
            e_team_size,
            banned_size,
            start_teams[i],
            start_e_teams[0],  // any enemy team can be used as all hero variations are removed
            banned
        );
    }

    // init starting enemy variables
    for (int i = 0; i < num_e_teams; i++) {
        e_teams[i] = team_bit_repr(e_team_size, start_e_teams[i]);
        e_legals[i] = legal_bit_repr(
            e_team_size,
            team_size,
            banned_size,
            start_e_teams[i],
            start_teams[0],
            banned
        );
    }

    // call root function to deal with specific selection type
    //
    // (i'd like to generalise these, as fundamentally they are
    // all doing the same thing, but they each have slight differences at
    // various stages that it doesn't seem worth it)
    int stage = team_size + e_team_size + banned_size;
    switch (draft[stage].selection) {
        case PICK:
            return root_pick(
                num_teams,
                num_e_teams,
                teams,
                e_teams,
                legals,
                e_legals,
                stage
            );

        case BAN:
            return root_ban(
                num_teams,
                num_e_teams,
                teams,
                e_teams,
                legals,
                e_legals,
                stage
            );

        case PICK_PICK:
            return root_pick_pick(
                num_teams,
                num_e_teams,
                teams,
                e_teams,
                legals,
                e_legals,
                stage
            );

        case PICK_BAN:
            return root_pick_ban(
                num_teams,
                num_e_teams,
                teams,
                e_teams,
                legals,
                e_legals,
                stage
            );

        case BAN_PICK:
            return root_ban_pick(
                num_teams,
                num_e_teams,
                teams,
                e_teams,
                legals,
                e_legals,
                stage
            );

        default:
            return (struct search_result) {};
    }
}


struct search_result root_pick(
    int num_teams,
    int num_e_teams,
    u64 teams[],
    u64 e_teams[],
    u64 legals[],
    u64 e_legals[],
    int stage
)
{
    int value = -INF;
    int best_hero;

    for (int h = 0; h < num_heroes; h++) {
        // directly skip hero if we know it isn't legal for any lineup
        if (!legal_for_any_lineup(h, num_teams, legals))
            continue;

        // value of hero is the min value
        // for each enemy starting lineup
        int h_value = INF;
        u64 hero = 1ULL << h;

        for (int e_team_i = 0; e_team_i < num_e_teams; e_team_i++) {
            // value of an enemy lineup is the max
            // value for each team starting lineup
            int e_team_value = -INF;

            for (int team_i = 0; team_i < num_teams; team_i++) {
                // still need to check for hero being legal
                // in this specific starting lineup
                if (!(legals[team_i] & hero))
                    continue;

                int child_value = -negamax(
                    e_teams[e_team_i],
                    teams[team_i] | hero,
                    e_legals[e_team_i] & h_infos[h].diff_h,
                    legals[team_i] & h_infos[h].diff_role_and_h,
                    stage + 1,
                    -INF,
                    -value    // use current best value
                );

                if (child_value > e_team_value)
                    e_team_value = child_value;

                // skip evaluating rest of team lineups if 
                // enemy already has a better value
                if (e_team_value >= h_value)
                    break;
            }

            if (e_team_value < h_value)
                h_value = e_team_value;

            // skip rest of enemy lineups if they already have a
            // lineup where team gets a less-than-best value
            if (h_value <= value)
                break;
        }

        // only updating after evaluating team best response
        // to every starting lineup enemy could use
        if (h_value > value) {
            value = h_value;
            best_hero = h;
        }
    }

    return (struct search_result) {.value = value, .best_hero = best_hero};
}


struct search_result root_ban(
    int num_teams,
    int num_e_teams,
    u64 teams[],
    u64 e_teams[],
    u64 legals[],
    u64 e_legals[],
    int stage
)
{
    int value = -INF;
    int best_hero;

    for (int h = 0; h < num_heroes; h++) {
        // if hero is legal for at least one enemy lineup we must
        // consider the response values of all enemy lineups (not
        // only those where it is legal) as its possible the enemy
        // can get a better value in one where it is illegal
        if (!legal_for_any_lineup(h, num_e_teams, e_legals))
            continue;

        int h_value = INF;
        
        for (int e_team_i = 0; e_team_i < num_e_teams; e_team_i++) {
            int e_team_value = -INF;

            for (int team_i = 0; team_i < num_teams; team_i++) {
                int child_value = -negamax(
                    e_teams[e_team_i],
                    teams[team_i],
                    e_legals[e_team_i] & h_infos[h].diff_h,
                    legals[team_i] & h_infos[h].diff_h,
                    stage + 1,
                    -INF,
                    -value
                );

                if (child_value > e_team_value)
                    e_team_value = child_value;

                if (e_team_value >= h_value)
                    break;
            }

            if (e_team_value < h_value)
                h_value = e_team_value;

            if (h_value <= value)
                break;
        }

        if (h_value > value) {
            value = h_value;
            best_hero = h;
        }
    }

    return (struct search_result) {.value = value, .best_hero = best_hero};
}


struct search_result root_pick_pick(
    int num_teams,
    int num_e_teams,
    u64 teams[],
    u64 e_teams[],
    u64 legals[],
    u64 e_legals[],
    int stage
)
{
    int value = -INF;
    int best_hero;
    int best_hero_2;

    for (int h = 0; h < num_heroes; h++) {
        // directly skip hero if we know it isn't legal for any lineup
        if (!legal_for_any_lineup(h, num_teams, legals))
            continue;

        // updated team legals only to allow for checking of second hero
        u64 updated_legals[num_teams];
        for (int i = 0; i < num_teams; i++) {
            updated_legals[i] = legals[i] & h_infos[h].diff_role_and_h;
        }

        for (int h2 = h + 1; h2 < num_heroes; h2++) {
            // directly skip if no lineup can second pick this hero
            if (!legal_for_any_lineup(h2, num_teams, updated_legals))
                continue;

            int h_pair_value = INF;

            for (int e_team_i = 0; e_team_i < num_e_teams; e_team_i++) {
                int e_team_value = -INF;

                for (int team_i = 0; team_i < num_teams; team_i++) {
                    // initial state for this enemy-team combo
                    u64 team = teams[team_i];
                    u64 e_team = e_teams[e_team_i];
                    u64 legal = legals[team_i];
                    u64 e_legal = e_legals[e_team_i];

                    // check and update state if first hero legal
                    if (!(legal & (1ULL << h)))
                        continue;
                    team |= (1ULL << h);
                    legal &= h_infos[h].diff_role_and_h;
                    e_legal &= h_infos[h].diff_h;

                    // check and update state if second hero legal
                    if (!(legal & (1ULL << h2)))
                        continue;
                    team |= (1ULL << h2);
                    legal &= h_infos[h2].diff_role_and_h;
                    e_legal &= h_infos[h2].diff_h;

                    // if both are normal we continue like root_pick
                    int child_value = -negamax(
                        e_team,
                        team,
                        e_legal,
                        legal,
                        stage + 2,
                        -INF,
                        -value
                    );

                    if (child_value > e_team_value)
                        e_team_value = child_value;

                    if (e_team_value >= h_pair_value)
                        break;
                }

                if (e_team_value < h_pair_value)
                    h_pair_value = e_team_value;

                if (h_pair_value <= value)
                    break;
            }

            if (h_pair_value > value) {
                value = h_pair_value;
                best_hero = h;
                best_hero_2 = h2;
            }
        }
    }

    return (struct search_result) {value, best_hero, best_hero_2};
}


struct search_result root_pick_ban(
    int num_teams,
    int num_e_teams,
    u64 teams[],
    u64 e_teams[],
    u64 legals[],
    u64 e_legals[],
    int stage
)
{
    int value = -INF;
    int best_hero;
    int best_hero_2;

    for (int h = 0; h < num_heroes; h++) {
        // directly skip pick hero if no team lineup can pick it
        if (!legal_for_any_lineup(h, num_teams, legals))
            continue;
        u64 pick_hero = 1ULL << h;

        // updated enemy legals only to allow for checking of ban hero
        u64 updated_e_legals[num_e_teams];
        for (int i = 0; i < num_e_teams; i++) {
            updated_e_legals[i] = e_legals[i] & h_infos[h].diff_h;
        }

        for (int h2 = 0; h2 < num_heroes; h2++) {
            // only skipping ban hero if illegal in all enemy lineups
            if (!legal_for_any_lineup(h2, num_e_teams, updated_e_legals))
                continue;

            int h_pair_value = INF;

            for (int e_team_i = 0; e_team_i < num_e_teams; e_team_i++) {
                int e_team_value = -INF;

                for (int team_i = 0; team_i < num_teams; team_i++) {
                    // initial state for this enemy-team combo
                    u64 team = teams[team_i];
                    u64 e_team = e_teams[e_team_i];
                    u64 legal = legals[team_i];
                    u64 e_legal = e_legals[e_team_i];

                    // update state for pick if legal
                    // for this specific team lineup
                    if (!(legal & pick_hero))
                        continue;
                    team |= pick_hero;
                    legal &= h_infos[h].diff_role_and_h;
                    e_legal &= h_infos[h].diff_h;

                    // update state for ban
                    legal &= h_infos[h2].diff_h;
                    e_legal &= h_infos[h2].diff_h;

                    int child_value = -negamax(
                        e_team,
                        team,
                        e_legal,
                        legal,
                        stage + 2,
                        -INF,
                        -value
                    );

                    if (child_value > e_team_value)
                        e_team_value = child_value;

                    if (e_team_value >= h_pair_value)
                        break;
                }

                if (e_team_value < h_pair_value)
                    h_pair_value = e_team_value;

                if (h_pair_value <= value)
                    break;
            }

            if (h_pair_value > value) {
                value = h_pair_value;
                best_hero = h;
                best_hero_2 = h2;
            }
        }
    }

    return (struct search_result) {value, best_hero, best_hero_2};
}


struct search_result root_ban_pick(
    int num_teams,
    int num_e_teams,
    u64 teams[],
    u64 e_teams[],
    u64 legals[],
    u64 e_legals[],
    int stage
)
{
    int value = -INF;
    int best_hero;
    int best_hero_2;

    for (int h = 0; h < num_heroes; h++) {
        // only skipping ban hero if illegal in all enemy lineups
        if (!legal_for_any_lineup(h, num_e_teams, e_legals))
            continue;

        // updated team legals only to allow for checking of pick hero
        u64 updated_legals[num_teams];
        for (int i = 0; i < num_teams; i++) {
            updated_legals[i] = legals[i] & h_infos[h].diff_h;
        }

        for (int h2 = 0; h2 < num_heroes; h2++) {
            // directly skip pick hero if no team lineup can pick it
            if (!legal_for_any_lineup(h2, num_teams, updated_legals))
                continue;
            u64 pick_hero = 1ULL << h2;

            int h_pair_value = INF;

            for (int e_team_i = 0; e_team_i < num_e_teams; e_team_i++) {
                int e_team_value = -INF;

                for (int team_i = 0; team_i < num_teams; team_i++) {
                    // initial state for this enemy-team combo
                    u64 team = teams[team_i];
                    u64 e_team = e_teams[e_team_i];
                    u64 legal = legals[team_i];
                    u64 e_legal = e_legals[e_team_i];

                    // update state for ban
                    legal &= h_infos[h].diff_h;
                    e_legal &= h_infos[h].diff_h;

                    // update state for pick if legal
                    // for this specific team lineup
                    if (!(legal & pick_hero))
                        continue;
                    team |= pick_hero;
                    legal &= h_infos[h2].diff_role_and_h;
                    e_legal &= h_infos[h2].diff_h;

                    int child_value = -negamax(
                        e_team,
                        team,
                        e_legal,
                        legal,
                        stage + 2,
                        -INF,
                        -value
                    );

                    if (child_value > e_team_value)
                        e_team_value = child_value;

                    if (e_team_value >= h_pair_value)
                        break;
                }

                if (e_team_value < h_pair_value)
                    h_pair_value = e_team_value;

                if (h_pair_value <= value)
                    break;
            }

            if (h_pair_value > value) {
                value = h_pair_value;
                best_hero = h;
                best_hero_2 = h2;
            }
        }
    }

    return (struct search_result) {value, best_hero, best_hero_2};
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


// ======================================================================
// I need a way to go from receiving a draft format and set of rewards in
// python to initialising the global variables required for calling
// searches. For now having python do most of the processing and 
// initialising individual elements seems easiest. However, I may want to 
// change this @Later. The following are used as part of the python 
// init_draft_ai function.

void set_role_r(int hero_num, int A_value, int B_value)
{
    role_rs[hero_num].A_value = A_value;
    role_rs[hero_num].B_value = B_value;
}


void set_synergy_r(int i, u64 heroes, int A_value, int B_value)
{
    synergy_rs[i].heroes = heroes;
    synergy_rs[i].A_value = A_value;
    synergy_rs[i].B_value = B_value;
}


void set_counter_r(int i, u64 heroes, u64 foes, int A_value, int B_value)
{
    counter_rs[i].heroes = heroes;
    counter_rs[i].foes = foes;
    counter_rs[i].A_value = A_value;
    counter_rs[i].B_value = B_value;
}


void set_draft_stage(int stage, int team, int selection)
{
    draft[stage].team = team;
    draft[stage].selection = selection;
}


void set_h_info(int hero_num, u64 same_role_and_h, u64 same_h)
{
    h_infos[hero_num].diff_role_and_h = ~same_role_and_h;
    h_infos[hero_num].diff_h = ~same_h;
}


void set_sizes(int heroes, int synergy_rs, int counter_rs, int draft)
{
    num_heroes = heroes;
    num_synergy_rs = synergy_rs;
    num_counter_rs = counter_rs;
    draft_len = draft;
}

// ======================================================================
