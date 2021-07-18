#define MAX_NUM_HEROES 64
#define MAX_SYNERGIES 20
#define MAX_COUNTERS  20  
#define MAX_DRAFT_LEN 24

#define INF 30000

// heroes represented by position in bit field
typedef unsigned long long u64;

// REWARDS
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


int negamax(u64 team, u64 e_team, u64 legal, u64 e_legal, int stage, int alpha, int beta);

int terminal_value(u64 team_A, u64 team_B);
