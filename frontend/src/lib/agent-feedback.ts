/**
 * Turns the fact checker's reason codes (e.g. "skill_not_in_evidence: Kafka")
 * into sentences a candidate can act on.
 */
const RULES: [RegExp, (match: RegExpMatchArray) => string][] = [
  [/skill_not_in_evidence: ([^;"]+)/g, (m) => `Your resume doesn't show ${m[1].trim()}.`],
  [/number_not_in_evidence: ([^;"]+)/g, (m) => `The figure "${m[1].trim()}" doesn't appear in your resume.`],
  [/quote_is_hedged/g, () => 'Your resume describes this as something you are learning, not experience you have.'],
  [/quote_not_in_resume/g, () => "The resume line this relies on couldn't be found."],
  [/no_evidence/g, () => 'Nothing in your resume backs this statement.'],
  [/adds_wording: ([^;"]+)/g, (m) => `Adds wording your original line doesn't contain (${m[1].trim()}). Check it's accurate.`],
  [/empty_rewrite/g, () => 'No usable suggestion was produced for this line.'],
  [/unknown evidence id/g, () => "Part of this couldn't be matched to your resume."],
];

export function explainProblems(problems: string[]): string[] {
  const messages = new Set<string>();
  for (const problem of problems) {
    for (const [pattern, message] of RULES) {
      for (const match of problem.matchAll(pattern)) {
        messages.add(message(match));
      }
    }
  }
  return [...messages];
}
