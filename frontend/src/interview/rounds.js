export const ROUNDS = [
  { id: 'dsa', icon: '🧩', title: 'DSA', blurb: 'Coding question, follow-ups, your code is tested.' },
  { id: 'behavioral', icon: '🗣️', title: 'Behavioral / HR', blurb: 'STAR-style questions about teamwork and mistakes.' },
  { id: 'sql', icon: '🗄️', title: 'SQL', blurb: 'Queries, joins, NULLs and indexes. Type your SQL.' },
  { id: 'resume', icon: '📄', title: 'Resume-based', blurb: 'Questions from your own projects. Needs a PDF.' },
  { id: 'mixed', icon: '🎯', title: 'Mixed', blurb: 'One DSA, one behavioral (or resume), one SQL.' },
]

// The scorecard always has the same 4 fields; their meaning depends on the round.
export const SCORE_LABELS = {
  dsa: { approach: 'Approach', complexity: 'Complexity', edge_cases: 'Edge cases', communication: 'Communication' },
  behavioral: { approach: 'Structure (STAR)', complexity: 'Depth & impact', edge_cases: 'Self-awareness', communication: 'Communication' },
  sql: { approach: 'Correctness', complexity: 'Performance thinking', edge_cases: 'NULLs & duplicates', communication: 'Communication' },
  resume: { approach: 'Technical depth', complexity: 'Ownership & impact', edge_cases: 'Trade-offs', communication: 'Communication' },
  mixed: { approach: 'Approach / correctness', complexity: 'Depth / performance', edge_cases: 'Edge cases / self-awareness', communication: 'Communication' },
}
export const needsEditor = (round) => round === 'dsa' || round === 'mixed'
