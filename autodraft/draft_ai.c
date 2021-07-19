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
    u64 hero = 1;  // represents hero 0 (first bit)
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