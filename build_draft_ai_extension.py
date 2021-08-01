""" Compile draft_ai C code into callable library from python. """

from cffi import FFI

ffibuilder = FFI()

ffibuilder.cdef(
    """
    typedef unsigned long long u64;

    // initialiser set up functions
    void set_role_r(int hero_num, int A_value, int B_value);
    void set_synergy_r(int i, u64 heroes, int A_value, int B_value);
    void set_counter_r(int i, u64 heroes, u64 foes, int A_value, int B_value);
    void set_draft_stage(int stage, int team, int selection);
    void set_h_info(int hero_num, u64 same_role_and_h, u64 same_h);
    void set_sizes(int heroes, int synergy_rs, int counter_rs, int draft);

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
    """
)

ffibuilder.set_source(
    '_draft_ai',
    """
    #include "autodraft/draft_ai.h"
    """,
    sources=['autodraft/draft_ai.c'],
)


if __name__ == "__main__":
    ffibuilder.compile(verbose=True)
