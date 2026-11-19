# Annual cohort steps instead of an ODE solver

The population model is the McKendrick–von Foerster equation, which becomes about 100 coupled ODEs when cut into one-year age groups. We do not pass these ODEs to a general solver such as `scipy.integrate.solve_ivp`. We step forward one year at a time and move each cohort up exactly one age group (the cohort-component method), because this is the exact solution on a one-year grid, while a general solver smears cohorts across neighbouring ages and blurs features such as the baby-boom generation.
