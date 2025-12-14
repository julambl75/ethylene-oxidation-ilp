#bias(":- #count { X : in_body(X) } < 1.").
#bias(":- #count { X : in_body(X) } > 6.").

#bias(":- lb(X, Y1), lb(X, Y2), Y1 != Y2.").
#bias(":- ub(X, Y1), ub(X, Y2), Y1 != Y2.").

#bias("penalty(50, head(X)) :- in_head(X).").
#bias("penalty(5, body(X)) :- in_body(X).").
%#bias("penalty(1000 / (1 + |Y2 - Y1|), X) :- lb(X, Y1), ub(X, Y2).").

#bias("intermediate(rule_has_head(X)) :- in_head(X).").
#final_bias(":- possible_head(X), not rule_has_head(X).").

#prob(0.1).
#prob(0.2).
#prob(0.3).
#prob(0.4).
#prob(0.5).
#prob(0.6).
#prob(0.7).
#prob(0.8).
#prob(0.9).
#prob(1.0).
