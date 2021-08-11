#define MAX_NUM_HEROES 64
#define MAX_SYNERGIES 50
#define MAX_COUNTERS  50  
#define MAX_DRAFT_LEN 24

#define INF 30000


// heroes represented by position in bit field
typedef unsigned long long u64;


// A transposition table is used to cache evaluated states. The
// information for a single entry can be packed into 64 bits. Only
// 16 bits are needed for the value and 2 bits for the type of value.
// This leaves 46 bits for storing upper bits of the state hash to
// resolve collisions. Therefore, at least 18 of the lower hash bits
// must be used to index into the table. Also, as exponentially more
// states are visited in later depths, all of which can be evaluated
// extremely quick, only the upper stages are saved (reduces overhead
// of constantly accessing memory and ensures that the states taking
// longer to evaluate are less likely to be replaced).
#define TT_IDX_BITS 0xFFFFFULL
#define MAX_TT_STAGE 7

enum tt_flag
{
    EXACT = 0,
    LOWERBOUND = 1,
    UPPERBOUND = 2
};

struct tt_entry
{
    u64 tag : 46;
    enum tt_flag flag : 2;
    int value : 16;
};


// Reward structs.
struct role_r
{
    // hero will be tracked by index in all role rewards
    int A_value;
    int B_value;
};

struct synergy_r
{
    u64 heroes;
    int A_value;
    int B_value;
};

struct counter_r
{
    u64 heroes;
    u64 foes;
    int A_value;
    int B_value;
};


// Holds all hero nums (indicated with a bit equal to 1) that play a
// a different role and are not the same underlying hero. Used to
// update legal actions with a single AND operation.
struct h_info
{
    u64 diff_role_and_h;  // for team after pick
    u64 diff_h;           // for enemy after pick or both teams after ban
};


// Draft format.
// set to match constants defined in ai_prep.py
// don't change without changing there as well
enum team 
{
    A = 0,  // these double as indices for an A/B pick in the
    B = 1,  // zobrist table so they MUST be kept as 0 and 1
};

#define BAN_KEYS 2  // index into zobrist table for a banned hero

enum selection 
{
    PICK = 0,
    BAN = 1,
    PICK_PICK = 2,
    PICK_BAN = 3,
    BAN_PICK = 4,
    BAN_BAN = 5,
};

struct draft_stage
{
    enum team team;
    enum selection selection;
};


// returned by outer search function
struct search_result
{
    int value;
    int best_hero;
    int best_hero_2;  // only applies for stages with a double selection
};


// search
int negamax(
    u64 team,
    u64 e_team,
    int *team_ptr,
    int *e_team_ptr,
    u64 legal,
    u64 e_legal,
    u64 hash,
    int stage,
    int alpha,
    int beta
);
int terminal_value(u64 team_A, u64 team_B);
int flex_negamax(
    int num_teams,
    int num_e_teams,
    u64 teams[],
    u64 e_teams[],
    u64 legals[],
    u64 e_legals[],
    u64 hashes[],
    u64 e_hashes[],
    u64 bans_hash,
    int stage,
    int alpha,
    int beta
);
int *init_team_heroes(u64 team, int *team_ptr);
int hero_in_team_update(
    int hero_num,
    enum team selecting_team,
    int num_teams,
    u64 teams[],
    u64 legals[],
    u64 hashes[],
    u64 new_teams[],
    u64 new_legals[],
    u64 new_hashes[]
);
void hero_out_of_team_update(int hero_num, int num_teams, u64 legals[], u64 new_legals[]);
struct search_result root_negamax(
    int num_teams,
    int num_e_teams,
    u64 teams[],
    u64 e_teams[],
    u64 legals[],
    u64 e_legals[],
    u64 hashes[],
    u64 e_hashes[],
    u64 bans_hash,
    int stage
);
struct search_result run_search(
    int num_teams_A,
    int num_teams_B,
    int team_A_size,
    int team_B_size,
    int banned_size,
    int** start_teams_A,
    int** start_teams_B,
    int* banned
);

// helpers
int legal_for_any_lineup(int hero_num, int num_teams, u64 legals[]);
u64 team_bit_repr(int team_size, int team_nums[]);
u64 legal_bit_repr(
    int team_size,
    int e_team_size,
    int banned_size,
    int team_nums[],
    int e_team_nums[],
    int banned_nums[]
);
u64 init_hash(int team_or_ban, int hero_nums_size, int hero_nums[]);

void switch_reward_team_values();
void clear_tt();

// set up functions used to init all global variables required for search
void set_role_r(int hero_num, int A_value, int B_value);
void set_synergy_r(int i, int heroes_size, int hero_nums[], int A_value, int B_value);
void set_counter_r(int i, int heroes_size, int hero_nums[], int foes_size, 
                   int foe_nums[], int A_value, int B_value);
void set_draft_stage(int stage, int team, int selection);
void set_h_info(int hero_num, int same_role_and_h_size, int same_role_and_h_nums[],
                int same_h_size, int same_h_nums[]);
void set_sizes(int heroes, int synergy_rs, int counter_rs, int draft);
void set_zobrist_key(int team_or_ban, int hero_num, u64 key);
