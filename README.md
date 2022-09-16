# Omnidraft

Extremely fast search engine—operating mainly at the level of individual bits—to discover the optimal actions, in accordance to supplied preferences, for the draft phase of any MOBA.

The bulk of the engine is written in C and located [here](https://github.com/abpalmarini/omnidraft/tree/main/ai). Most utility, prep and wrapper functionality (whose speed is not essential) is written in python and located [here](https://github.com/abpalmarini/omnidraft/blob/main/src/main/python/ai/draft_ai.py). The remaining code constructs an app for using the engine.

### Table of Contents

- [Introduction](#introduction)
- [Transforming drafts into a zero-sum game](#transforming-drafts-into-a-zero-sum-game)
- [Engine](#engine)
  - [Speed](#speed)
  - [Main features](#main-features)
  - [Limitations](#limitations)
- [App](#app)

### Introduction

A [MOBA](https://en.wikipedia.org/wiki/Multiplayer_online_battle_arena) consists of two teams, with each player (most commonly 5 per team) controlling a unique hero, competing to destroy each other's base located at opposite ends of a battlefield. Prior to a game, teams will alternate in both selecting heroes to play and banning heroes from the available options in 20 to 30 second intervals. This is known as the _draft_. The unique design and special abilities of a hero can complement or counter those of another. The draft, therefore, plays a vital role in a team's success—get a bad draft and you are entering the game disadvantaged. 

The draft has a simple structure. Despite being carried out by two teams it can be viewed as a 2-player, sequential, deterministic and perfect information game—like chess or Go. Additionally, like chess or Go, finding an optimal action is difficult due to the large number of possible drafts: for example, there are currently $4 \times 10^{43}$ in the world's most popular MOBA (League of Legends). However, unlike chess or Go, drafting is unique in that there is no definitive winner: an outcome preferred by one team may be disliked by another because of factors such as the team's (and current opposition’s) individual playstyles, strategies and more in the main game where the drafted heroes are used.

Thus, to create a system that can out-draft opponents at the highest level of competition, two things are required. First, a framework in which drafts can be ranked as better or worse so that objectively optimal actions are brought into existence. Second, a method that can tractably find these optimal actions. 

### Transforming drafts into a zero-sum game

Turning the draft phase from a game with no formal winner into a zero-sum game requires a method that can evaluate every pair of resulting hero compositions. Additionally, the evaluation should not be general: it should depend on who will be using the drafted compositions. This can be achieved with a reward system that is briefly described below. Moreover, I propose that this simple system is able to explicitly and adequately capture any and all knowledge one would use when carrying out a draft.

A set of rewards consisting of only three types—each based on gaining a certain hero or combination of heroes—are created beforehand to reflect a player's thoughts about the intended game. Each reward contains two values representing how desirable the reward is for each team. At the end of a draft each side is granted their respective value associated with any reward whose requirements they meet. The difference in each sides total values provides the single numbered evaluation of the draft. The three rewards are:

- **Role reward:** Having hero $h$ in role $r$.
- **Synergy reward:** Having each hero in the set $S$—each in one of their specified roles.
- **Counter reward:** Having each hero in the set $S$ (possibly a singleton)—each in one of their specified roles—and the opposing team has each hero in the set $C$ (possibly a singleton)—each in one of their specified roles. 

This system turns the draft into a zero-sum game with a well defined Nash equilibrium. All drafts have a fixed evaluation except in the case where a counter reward (that requires the relevant heroes on both sides to be in specific roles) could be granted depending on the role assignment chosen by either team. In such cases it is possible for the value to never converge as each side could alternate indefinitely in switching their role assignment to gain more value based on the opposition's current role assignment. However, this does not effect the Nash equilibrium as its solution here is to take actions resulting in the best _guaranteed_ value.

### Engine

With the reward system in place the draft (now formulated as a two player zero-sum game) can be solved in a straightforward manner with the minimax theorem (and an alpha-beta search implementation). Unfortunately, no straightforward implementation (as I repeatedly found out) is able to solve the draft perfectly in a practical time. (For an alternative approach, based on DeepMind's AlphaZero, that doesn't attempt to solve the draft perfectly see [deepdraft](https://github.com/abpalmarini/deepdraft).) Omnidraft is able to achieve this by employing several techniques (briefly described below) that take advantage of the draft's structure to both prune nodes from the search tree and evaluate remaining nodes extremely quickly by minimising the total number of operations executed in hardware[^1].

[^1]: Unfortunately, the speed comes at a cost: there is a specific case where the engine won't return the game theory optimal action. See [Limitations](#limitations) for more details.

###### Speed

For an example of omnidraft's speed: a draft situation that took a general minimax algorithm written in python 25 minutes to solve, took this engine only 0.12 seconds (that is, 0.008% of the time). The omnidraft engine is able to reach speeds greater than 222 million nodes per second using only 12 threads on my 2019 MacBook Pro. For comparison, during game 1 of the 2020/21 Top Chess Engine Championship (TCEC) finals the winning chess engine Stockfish reached a maximum of 147 million nodes per second on specialised hardware with 172 threads. 

###### Main features

1. The core aspect of omnidraft that gives rise to its speed is reducing as much of the problem as possible to a few bit strings in such a way that all things necessary for creating and searching a game tree—namely, updating the game state, determining legal actions and evaluating terminal nodes—can each be performed with only a few bitwise, comparison or addition operations that are directly supported by the hardware. For details on how this is achieved for each case, please refer to the code and the associated comments.
2. For a given state in a draft, any permutation of either team's actions will lead to that same game state. Consequently, many nodes (and their subtrees) may be reevaluated unnecessarily. Reevaluations are mitigated with Zobrist hashing—that is, assigning each action type a random bit string so that the sequential bitwise XOR of any permutation of the same actions will create the same hash—and a transposition table that efficiently packs a node's value, hash and metadata into a single hardware word. Additionally, as nodes increase exponentially with depth, the depth to which nodes are cached can be adjusted based on available memory to both reduce the chance of smaller-subtree-nodes overwriting larger-subtree-nodes and finding the optimal tradeoff between the time to access memory vs evaluation.
3. At the root node, actions are evaluated in parallel—where each thread is dynamically allocated to the next unevaluated action. Consequently, the engine is evaluating more nodes at once with little overhead in allocation and locking (to prevent race conditions) due to the small number of child nodes stemming from the root.

###### Limitations

The main factor contributing to the engine's speed (feature 1) required reframing the draft as a slightly different game with slightly different rules and then adapting to solve the problems that arise as a result. This allows optimal actions to be discovered with unmatched speeds. Unfortunately, as a consequence of the reformulation, there is a specific draft case where the engine will return a suboptimal action. (Even more unfortunate is how late into development I realised this.)[^2] This does not take away from the engine's power as a competitive drafter—in almost all situations the game theory optimal action will be returned and when it doesn't the action is still likely to be good. However, if I was not intending to solve the draft perfectly—as I was with this engine—then other approaches could have been taken. I made many attempts to resolve this issue; however, each solution sacrificed the original engine's speed. (It was after reimplementing the engine in vain for the fourth time that I decided to throw in the towel and move onto more interesting things.)

[^2]: Specifically, the case arises when _all_ of the following are true: i) the opponents can respond to a suboptimal action with a hero who can play more than one role, ii) your response to that hero in each role individually results in a value greater than would be gained with the true worst-case optimal action and iii) realising each of those values involves different response actions (which is implied by ii) if the initial action is suboptimal). Therefore, no matter what response is taken to the opponent's response to your initial action, the opponent can then switch their hero's role to gain more value—which, if ii) is true, will leave you with a value less than the worst-case scenario value of an alternate initial action.

Another limitation is that the engine can only support up to 64 role rewards because that this is the number of bits in a unit of data used by most processors. Anymore and the engine would lose its ability to update the game state, determine legal actions and evaluate terminal nodes with only a few hardware operations—as mentioned above. (It's possible that this could be increased to 128—by storing certain information across two words and performing an additional operation when required—without a significant loss in speed, but I never tested it.)

### App

When I undertook this project I never planned to do any UI work—the project was intended as a means to explore, and test my understanding of, various subfields of AI: I had to understand what was going on to know how and why it could be useful for my problem. 

However, what good is an engine that can't be used? I believed I had a powerful tool that could discover the optimal actions while drafting and thus be extremely useful in competitive settings. To this end, I created a (usability-focused) interface in which users could create, edit and view rewards; experiment with how those rewards would combine in different team compositions; and, of course, run the engine to find an optimal action for a given draft history and reward set. Example screenshots:

<img width="1625" alt="view rewards" src="https://user-images.githubusercontent.com/59516601/190640112-622b00c3-55a5-48b9-bb49-c157eaa9b6e6.png">

<img width="1625" alt="create rewards" src="https://user-images.githubusercontent.com/59516601/190640212-9d722ff4-5be8-4061-bccf-ca4d9a9ef47e.png">

<img width="1625" alt="run search" src="https://user-images.githubusercontent.com/59516601/190640296-f20627ac-68de-48d6-ba41-756c1c809e11.png">
 
