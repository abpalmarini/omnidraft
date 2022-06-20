""" Compile draft_ai C code into callable library from python. """

from cffi import FFI

ffibuilder = FFI()

ffibuilder.cdef(
    """
    typedef unsigned long long u64;

    struct constants_s
    {
        int max_num_heroes;
        int max_synergy_rs;
        int max_counter_rs;
        int max_draft_len;
        int a;
        int b;
        int ban_keys;
        int pick;
        int ban;
        int pick_pick;
        int pick_ban;
        int ban_pick;
        int ban_ban;
        int inf;
    };

    // ensure python stays consistent with constants defined in draft_ai.h
    struct constants_s get_constants();

    // initialiser set up functions
    void set_role_r(int hero_num, int A_value, int B_value);
    void set_synergy_r(int i, int heroes_size, int hero_nums[], int A_value, int B_value);
    void set_counter_r(int i, int heroes_size, int hero_nums[], int foes_size, 
                       int foe_nums[], int A_value, int B_value);
    void set_draft_stage(int stage, int team, int selection);
    void set_h_info(int hero_num, int same_role_and_h_size, int same_role_and_h_nums[],
                    int same_h_size, int same_h_nums[]);
    void set_sizes(int heroes, int synergy_rs, int counter_rs, int draft);
    void set_zobrist_key(int team_or_ban, int hero_num, u64 key);

    // search
    struct search_result
    {
        int value;
        int best_hero;
        int best_hero_2;  // only applies for stages with a double selection
    };
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

    // utils
    void clear_tt();
    void write_tt_and_zobrist_keys(const char *filename);
    void read_tt_and_zobrist_keys(const char *filename);
    """
)

ffibuilder.set_source(
    '_draft_ai',
    """
    #include "omnidraft/draft_ai.h"
    """,
    sources=['omnidraft/draft_ai.c'],
    extra_compile_args=['-fopenmp'],
    extra_link_args=['-fopenmp'],
)


if __name__ == "__main__":
    ffibuilder.compile(verbose=True)
