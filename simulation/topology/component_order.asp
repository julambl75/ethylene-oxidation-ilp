succ(A, B) :- node(A, _), node(B, _), pipe(A, _, B, _).
%succ(A, B) :- node(A, _), node(B, _), connector(A, _, B, _).
succ(A, B) :- node(A, _), node(B, _), connector(A, _, B, _), connector(_, _, A, _).

path(A, B) :- succ(A, B).
path(A, B) :- succ(A, C), path(C, B).

#show succ/2.
#show path/2.
