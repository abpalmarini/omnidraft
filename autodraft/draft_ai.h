#define MAX_NUM_HEROES 64
#define MAX_SYNERGIES 50
#define MAX_COUNTERS  50  
#define MAX_DRAFT_LEN 24

#define INF 30000

// heroes represented by position in bit field
typedef unsigned long long u64;

// reward structs
struct role_r
{
    // hero will tracked by index in all role rewards
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


// set to match constants defined in ai_prep.py
// don't change without changing there as well
enum team 
{
    A = 0, 
    B = 1,
};

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
int negamax(u64 team, u64 e_team, u64 legal, u64 e_legal, int stage, int alpha, int beta);
int terminal_value(u64 team_A, u64 team_B);
int run_search(int team_A_nums[], int team_B_nums[], int banned_nums[]);

// set up functions used to init all global variables required for search
void set_role_r(int hero_num, int A_value, int B_value);
void set_synergy_r(int i, u64 heroes, int A_value, int B_value);
void set_counter_r(int i, u64 heroes, u64 foes, int A_value, int B_value);
void set_draft_stage(int stage, int team, int selection);
void set_h_info(int hero_num, u64 same_role_and_h, u64 same_h);
void set_sizes(int heroes, int synergy_rs, int counter_rs, int draft);
