const quotes = [
  {
    text: "You don't need more motivation. You need a system that works when motivation fails.",
    category: "systems"
  },
  {
    text: "The gap between where you are and where you want to be is filled with the days you didn't show up.",
    category: "consistency"
  },
  {
    text: "Most people quit right before the compound effect kicks in. That's why most people don't compound.",
    category: "compounding"
  },
  {
    text: "You're not behind. You're just on a timeline that isn't Instagram's highlight reel.",
    category: "perspective"
  },
  {
    text: "Discipline is just the ability to keep promises to yourself when no one's watching.",
    category: "discipline"
  },
  {
    text: "The work you avoid is usually the work that matters most.",
    category: "resistance"
  },
  {
    text: "Waiting for clarity is a form of procrastination. Clarity comes from action, not before it.",
    category: "action"
  },
  {
    text: "Your future self is begging you to do the boring work today.",
    category: "future-self"
  },
  {
    text: "You don't find time. You make time by deciding what matters less.",
    category: "priorities"
  },
  {
    text: "The person you'll be in five years is determined by what you tolerate today.",
    category: "standards"
  },
  {
    text: "Motivation is a feeling. Commitment is a decision. Only one survives a bad Tuesday.",
    category: "commitment"
  },
  {
    text: "You're not tired. You're uninspired by the life you're currently building.",
    category: "alignment"
  },
  {
    text: "The hardest part isn't starting. It's continuing when the novelty wears off and the results haven't shown up yet.",
    category: "persistence"
  },
  {
    text: "Everyone wants the outcome. Few want the process. That's why the outcome is rare.",
    category: "process"
  },
  {
    text: "Your environment shapes your behavior more than your willpower shapes your environment.",
    category: "environment"
  },
  {
    text: "Stop waiting for the version of you that feels ready. She's not coming. The unready version has to do the work.",
    category: "readiness"
  },
  {
    text: "A year from now you'll wish you started today. This is true every single day.",
    category: "regret"
  },
  {
    text: "The quality of your life is the quality of your habits. Nothing more, nothing less.",
    category: "habits"
  },
  {
    text: "You don't rise to the level of your goals. You fall to the level of your systems.",
    category: "systems"
  },
  {
    text: "Comfort is the enemy of growth. But discomfort without direction is just suffering.",
    category: "growth"
  },
  {
    text: "Most advice is just someone telling you what worked for their specific context. Your context is different.",
    category: "advice"
  },
  {
    text: "The days that feel like nothing happened are the days the foundation gets poured.",
    category: "invisible-work"
  },
  {
    text: "You can't heal in the same environment that made you sick. Same applies to growth.",
    category: "environment"
  },
  {
    text: "Perfectionism isn't high standards. It's fear wearing a tuxedo.",
    category: "perfectionism"
  },
  {
    text: "The cost of discipline is paid upfront. The cost of regret is paid forever with interest.",
    category: "regret"
  },
  {
    text: "You're not 'figuring it out.' You're avoiding the decision you already know is right.",
    category: "decision"
  },
  {
    text: "Small wins look unimpressive on a resume. They look like character in the mirror.",
    category: "character"
  },
  {
    text: "The only thing worse than failing is succeeding at something that doesn't matter.",
    category: "meaning"
  },
  {
    text: "Your anxiety is usually just your body preparing for a future that hasn't happened yet.",
    category: "anxiety"
  },
  {
    text: "People overestimate what they can do in a month. Underestimate what they can do in a decade. The math is ruthless.",
    category: "time"
  },
  {
    text: "You don't need more information. You need the courage to act on what you already know.",
    category: "courage"
  },
  {
    text: "The version of you that exists only in your head is perfect. The version that exists in reality is built.",
    category: "reality"
  },
  {
    text: "Burnout isn't from working too hard. It's from working too hard on the wrong things with the wrong people for the wrong reasons.",
    category: "burnout"
  },
  {
    text: "Your calendar is a more honest biography than your resume.",
    category: "honesty"
  },
  {
    text: "The problem isn't that you're not motivated. The problem is you're motivated by the wrong things.",
    category: "motivation"
  },
  {
    text: "Consistency beats intensity because intensity is a feeling and consistency is a structure.",
    category: "consistency"
  },
  {
    text: "You don't need a new plan. You need to follow the old plan on the days you don't feel like it.",
    category: "follow-through"
  },
  {
    text: "The people who tell you 'it's not that simple' are usually the ones benefiting from the complexity.",
    category: "simplicity"
  },
  {
    text: "Your standards for yourself are the only ones that matter. Everyone else is grading on a curve.",
    category: "standards"
  },
  {
    text: "The uncomfortable conversation you're avoiding is the one that changes everything.",
    category: "difficult-conversations"
  },
  {
    text: "You're not 'behind in life.' You're just comparing your Chapter 3 to someone else's Chapter 12.",
    category: "comparison"
  },
  {
    text: "Freedom isn't doing whatever you want. It's being able to do what you committed to even when you don't want to.",
    category: "freedom"
  },
  {
    text: "The thing you're most afraid to do is usually the thing you most need to do.",
    category: "fear"
  },
  {
    text: "Waiting for inspiration is a luxury of amateurs. Professionals show up and create the conditions for inspiration.",
    category: "professionalism"
  },
  {
    text: "Your life changes the day you realize you're the one writing the script, not the one auditioning for it.",
    category: "agency"
  },
  {
    text: "Most problems aren't solved by adding more. They're solved by removing what doesn't belong.",
    category: "subtraction"
  },
  {
    "text": "The gap between knowing and doing is where dreams go to die.",
    category: "execution"
  },
  {
    text: "You don't build a life you love by accident. You build it by a thousand deliberate choices.",
    category: "intentionality"
  },
  {
    text: "The narrative you tell yourself about why you can't is the only thing actually stopping you.",
    category: "narrative"
  },
  {
    text: "Competence compounds. So does incompetence. Choose your daily reps carefully.",
    category: "competence"
  },
  {
    text: "The most dangerous addiction isn't substances. It's the comfort of familiar misery.",
    category: "comfort"
  },
  {
    text: "You can't negotiate with reality. You can only accept it and act accordingly.",
    category: "reality"
  },
  {
    text: "The person who moves the mountain starts by carrying small stones. The person who watches writes a book about how heavy mountains are.",
    category: "action-vs-commentary"
  },
  {
    text: "Your potential is a debt you owe to the person you could become.",
    category: "potential"
  },
  {
    text: "Clarity doesn't come from thinking harder. It comes from doing the thing badly until you understand it.",
    category: "clarity"
  },
  {
    text: "The best time to fix the roof was when the sun was shining. The second best time is now, while it's raining, while you're wet, while it's miserable.",
    category: "timing"
  },
  {
    text: "You are not your thoughts. You are the one who decides which thoughts get acted on.",
    category: "agency"
  },
  {
    text: "Resentment is drinking poison and expecting the other person to die. Forgiveness is putting the glass down.",
    category: "forgiveness"
  },
  {
    text: "The goal isn't to be better than others. The goal is to be better than you were yesterday, consistently.",
    category: "progress"
  },
  {
    text: "Excuses are the stories we tell ourselves to make quitting feel like a reasonable decision.",
    category: "excuses"
  },
  {
    text: "You don't get what you wish for. You get what you work for. You keep what you build systems for.",
    category: "systems"
  },
  {
    text: "The hardest person to lead is yourself. The most important person to lead is yourself.",
    category: "self-leadership"
  },
  {
    text: "A year of 'someday' equals zero days of progress. A day of 'today' equals one.",
    category: "today"
  },
  {
    text: "You're not a procrastinator. You're just practicing the skill of not doing hard things. Practice the other skill.",
    category: "identity"
  },
  {
    text: "The mountain doesn't care about your feelings. It only cares if you keep climbing.",
    category: "indifference"
  },
  {
    text: "Most people want the reward without the risk. The reward IS the risk paid off.",
    category: "risk"
  },
  {
    text: "Your future is built in the boring hours no one sees.",
    category: "invisible-work"
  },
  {
    text: "Stop managing your time. Start managing your energy. Time is fixed. Energy is renewable if you respect it.",
    category: "energy"
  },
  {
    text: "The only way out is through. The only way through is one step. The only way to take one step is now.",
    category: "now"
  }
];

function getRandomQuote() {
  return quotes[Math.floor(Math.random() * quotes.length)];
}

function getQuotesByCategory(category) {
  return quotes.filter(q => q.category === category);
}

function getCategories() {
  return [...new Set(quotes.map(q => q.category))];
}

function getQuoteByCategory(category) {
  const filtered = getQuotesByCategory(category);
  return filtered[Math.floor(Math.random() * filtered.length)];
}

export {
  quotes,
  getRandomQuote,
  getQuotesByCategory,
  getCategories,
  getQuoteByCategory
};