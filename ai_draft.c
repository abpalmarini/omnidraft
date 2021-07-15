#include "ai_draft.h"

int num_heroes;
int num_synergy_rs;
int num_counter_rs;
int draft_len;

struct role_r role_rs[MAX_NUM_HEROES];
struct synergy_r synergy_rs[MAX_SYNERGIES];
struct counter_r counter_rs[MAX_COUNTERS];

struct h_info h_infos[MAX_NUM_HEROES];

struct draft_stage draft[MAX_DRAFT_LEN]; 


int negamax(u64 team, u64 e_team, u64 legal, u64 e_legal, int stage, int alpha, int beta)
{
    if (stage == draft_len)
        // since B has last pick in draft it is always
        // guaranteed that team is A and e_team is B
        return terminal_value(team, e_team);

    return 0;
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
