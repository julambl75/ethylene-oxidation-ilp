#bias("penalty(3, head(X)) :- in_head(X).").
#bias("penalty(1, body(X)) :- in_body(X).").

#bias(":- #count { X : in_body(X) } < 1.").
#bias(":- N = #count { X : in_body(X) }, N = #count { X : in_body(X), X = measured(_, normal) }.").
#bias(":- in_head(measured(_, normal)).").

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
