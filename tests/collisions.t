Setup:

  $ alias xt="python $TESTDIR/../t.py --task-dir `pwd` --list test"

Make some tasks that collide in their first letter:

  $ xt 1
  3
  $ xt 2
  d
  $ xt 3
  7
  $ xt 4
  1
  $ xt 5
  a
  $ xt 6
  c
  $ xt 7
  9
  $ xt 8
  f
  $ xt 9
  0
  $ xt 10
  b
  $ xt 11
  17
  $ xt 12
  7b
  $ xt 13
  bd
  $ xt 14
  fa
  $ xt
  0  - 9
  17 - 11
  1b - 4
  3  - 1
  77 - 3
  7b - 12
  9  - 7
  a  - 5
  b1 - 10
  bd - 13
  c  - 6
  d  - 2
  fa - 14
  fe - 8

Even more ambiguity:

  $ xt 1test
  e
  $ xt 2test
  5
  $ xt 3test
  95
  $ xt 4test
  36
  $ xt 5test
  2
  $ xt 6test
  14
  $ xt 7test
  a1
  $ xt 8test
  07
  $ xt 9test
  0e
  $ xt 10test
  b10
  $ xt 11test
  6
  $ xt 12test
  8
  $ xt 13test
  c7
  $ xt 14test
  ef
  $ xt
  07  - 8test
  0a  - 9
  0e  - 9test
  14  - 6test
  17  - 11
  1b  - 4
  2   - 5test
  35  - 1
  36  - 4test
  5   - 2test
  6   - 11test
  77  - 3
  7b  - 12
  8   - 12test
  90  - 7
  95  - 3test
  a1  - 7test
  ac  - 5
  b10 - 10test
  b1d - 10
  bd  - 13
  c1  - 6
  c7  - 13test
  d   - 2
  ee  - 1test
  ef  - 14test
  fa  - 14
  fe  - 8

