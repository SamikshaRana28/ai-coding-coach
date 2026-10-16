// The AI review cards - same six cards as the Code Analyzer page.
// (CodeAnalyzer.jsx keeps its own private copy; it is intentionally left untouched.)

const COLORS = {
  blue: 'border-blue-200 bg-blue-50',
  purple: 'border-purple-200 bg-purple-50',
  red: 'border-red-200 bg-red-50',
  green: 'border-green-200 bg-green-50',
  amber: 'border-amber-200 bg-amber-50',
  indigo: 'border-indigo-200 bg-indigo-50',
}

function FeedbackCard({ title, content, color }) {
  return (
    <div className={`rounded-lg p-4 border ${COLORS[color]}`}>
      <h3 className="font-semibold text-sm mb-1">{title}</h3>
      <p className="text-sm text-slate-700 whitespace-pre-wrap">{content}</p>
    </div>
  )
}

export default function ReviewPanel({ review }) {
  return (
    <div className="space-y-3">
      <FeedbackCard title="⏱️ Time Complexity" content={review.time_complexity} color="blue" />
      <FeedbackCard title="💾 Space Complexity" content={review.space_complexity} color="purple" />
      <FeedbackCard title="🐛 Bugs" content={review.bugs} color="red" />
      <FeedbackCard title="✨ Better Approach" content={review.better_approach} color="green" />
      <FeedbackCard title="🔗 Similar Questions" content={review.similar_questions} color="amber" />
      <FeedbackCard title="🎤 Interviewer Questions" content={review.interviewer_questions} color="indigo" />
    </div>
  )
}
