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
            int team_value = negamax(    // swtich to normal negamax
                teams[i],
                e_teams[0],
                legals[i],
                e_legals[0],
                stage,
                alpha,
                beta
            );

            if (team_value >= value)
                value = team_value;

            if (value >= alpha)
                alpha = value;

            // can skip other lineups if enemy has better options
            if (alpha >= beta)
                break;
        }

        return value;
    } else if (stage == draft_len) {
        // for each A lineup find best (min) value B can get
        // then take best (max) value A can get as final value
        // (each team gets their best lineup if terminal state)
        int value_max = -INF;

        for (int i = 0; i < num_teams; i++) {
            int value_min = INF;

            for (int j = 0; j < num_e_teams; j++) {
                int value = terminal_value(teams[i], e_teams[j]);

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
    }

    // if there are multiple enemy lineups and its not a terminal 
    // state, then each legal hero is searched to get state value
    int value = -INF;
    switch (draft[stage].selection) {
        case PICK:
            for (int h = 0; h < num_heroes; h++) {
                u64 teams_p[num_teams];
                u64 legals_p[num_teams];
                int num_teams_p = hero_in_team_update(
                    h,
                    num_teams,
                    teams,
                    legals,
                    teams_p,
                    legals_p
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
                    stage + 1,
                    -beta,
                    -alpha
                );

                if (child_value >= value)
                    value = child_value;

                if (value >= alpha)
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
                    stage + 1,
                    -beta,
                    -alpha
                );

                if (child_value >= value)
                    value = child_value;

                if (value >= alpha)
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
                int num_teams_p = hero_in_team_update(
                    h,
                    num_teams,
                    teams,
                    legals,
                    teams_p,
                    legals_p
                );

                if (num_teams_p == 0)
                    continue;

                u64 e_legals_p[num_e_teams];
                hero_out_of_team_update(h, num_e_teams, e_legals, e_legals_p);

                for (int h2 = h + 1; h2 < num_heroes; h2++) {
                    // update lineups for second pick
                    u64 teams_pp[num_teams_p];
                    u64 legals_pp[num_teams_p];
                    int num_teams_pp = hero_in_team_update(
                        h2,
                        num_teams_p,
                        teams_p,
                        legals_p,
                        teams_pp,
                        legals_pp
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
                        stage + 2,
                        -beta,
                        -alpha
                    );

                    if (child_value >= value)
                        value = child_value;

                    if (value >= alpha)
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
                int num_teams_p = hero_in_team_update(
                    h,
                    num_teams,
                    teams,
                    legals,
                    teams_p,
                    legals_p
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
                        stage + 2,
                        -beta,
                        -alpha
                    );

                    if (child_value >= value)
                        value = child_value;

                    if (value >= alpha)
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

                for (int h2 = 0; h2 < num_heroes; h2++) {
                    // update lineups for pick
                    u64 teams_bp[num_teams];
                    u64 legals_bp[num_teams];
                    int num_teams_bp = hero_in_team_update(
                        h2,
                        num_teams,
                        teams,
                        legals_b,
                        teams_bp,
                        legals_bp
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
                        stage + 2,
                        -beta,
                        -alpha
                    );

                    if (child_value >= value)
                        value = child_value;

                    if (value >= alpha)
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
                        stage + 2,
                        -beta,
                        -alpha
                    );

                    if (child_value >= value)
                        value = child_value;

                    if (value >= alpha)
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
// Updates all team lineups and legal actions where it is possible to
// select the given hero, returning how many new lineups there are.
//
int hero_in_team_update(
    int hero_num,
    int num_teams,
    u64 teams[],
    u64 legals[],
    u64 new_teams[],
    u64 new_legals[]
)
{
    int new_num_teams = 0;
    u64 hero = 1ULL << hero_num;

    for (int i = 0; i < num_teams; i++) {
        if (legals[i] & hero) {
            // only update state for a lineup where hero is legal
            new_teams[new_num_teams] = teams[i] | hero;
            new_legals[new_num_teams] = legals[i] & h_infos[hero_num].diff_role_and_h;
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
// Outer search function. Eventually will be able to take in any 
// history of hero num lineups for both teams and bans, initialise
// bit format variables, then find the value of selecting each
// legal hero to return optimal value and action(s).
//
struct search_result run_search(
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

    // eventually this function will need to track optimal action at root
    // (for now just returning value from flex search)
    int value = flex_negamax(
        num_teams,
        num_e_teams,
        teams,
        e_teams,
        legals,
        e_legals,
        team_size + e_team_size + banned_size,
        -INF,
        INF
    );

    return (struct search_result) {.value = value};
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
