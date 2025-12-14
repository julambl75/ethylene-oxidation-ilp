prediction :- predicted(_).
prediction(no_failures) :- not prediction.

tp(X) :- class(X), predicted(X), expected(X).
tn(X) :- class(X), not predicted(X), not expected(X).
fp(X) :- class(X), predicted(X), not expected(X).
fn(X) :- class(X), not predicted(X), expected(X).

n_tp(N) :- N = #count { X : tp(X) }.
n_tn(N) :- N = #count { X : tn(X) }.
n_fp(N) :- N = #count { X : fp(X) }.
n_fn(N) :- N = #count { X : fn(X) }.

#show n_tp/1.
#show n_tn/1.
#show n_fp/1.
#show n_fn/1.
