import { useEffect, useState } from 'react'
import { getModelEvaluation, getDatasetStats } from '../api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts'

function ConfusionMatrix({ matrix, labels, title }) {
  const max = Math.max(...matrix.flat())
  return (
    <div>
      <h3 className="font-semibold mb-2">{title}</h3>
      <div className="inline-grid" style={{ gridTemplateColumns: `auto repeat(${labels.length}, 40px)` }}>
        <div></div>
        {labels.map((l) => (
          <div key={l} className="text-xs text-center font-medium p-1 rotate-45 origin-bottom-left">{l}</div>
        ))}
        {matrix.map((row, i) => (
          <>
            <div key={`label-${i}`} className="text-xs font-medium p-1 text-right pr-2">{labels[i]}</div>
            {row.map((val, j) => (
              <div
                key={`${i}-${j}`}
                className="text-xs text-center p-2 border border-white"
                style={{
                  backgroundColor: i === j
                    ? `rgba(34,197,94,${val / max})`
                    : `rgba(239,68,68,${val / max})`,
                }}
              >
                {val}
              </div>
            ))}
          </>
        ))}
      </div>
    </div>
  )
}

function MetricsCard({ name, metrics, highlight }) {
  return (
    <div className={`rounded-xl p-4 border ${highlight ? 'border-blue-500 bg-blue-50' : 'border-slate-200 bg-white'}`}>
      <h3 className="font-bold text-lg mb-2 flex items-center gap-2">
        {name} {highlight && <span className="text-sm bg-blue-500 text-white px-2 py-0.5 rounded-full">Winner 🏆</span>}
      </h3>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>Accuracy: <span className="font-semibold">{metrics.accuracy}</span></div>
        <div>F1 (macro): <span className="font-semibold">{metrics.f1_macro}</span></div>
        <div>F1 (weighted): <span className="font-semibold">{metrics.f1_weighted}</span></div>
        <div>ROC-AUC: <span className="font-semibold">{metrics.roc_auc}</span></div>
        <div>CV F1 mean: <span className="font-semibold">{metrics.cv_f1_mean}</span></div>
        <div>CV F1 std: <span className="font-semibold">±{metrics.cv_f1_std}</span></div>
      </div>
    </div>
  )
}

export default function ModelEvaluation() {
  const [data, setData] = useState(null)
  const [stats, setStats] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getModelEvaluation().then((res) => setData(res.data)).catch((e) => setError(e.message))
    getDatasetStats().then((res) => setStats(res.data)).catch(() => {})
  }, [])

  if (error) return <div className="text-red-600">Error loading data: {error}. Is the backend running on port 8000?</div>
  if (!data) return <div>Loading model evaluation...</div>

  const winnerKey = data.winner === 'XGBoost' ? 'xgboost' : 'random_forest'
  const loserKey = winnerKey === 'xgboost' ? 'random_forest' : 'xgboost'

  const f1ChartData = data.class_labels.map((label) => ({
    topic: label,
    XGBoost: data.xgboost.per_class_f1[label],
    'Random Forest': data.random_forest.per_class_f1[label],
  }))

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">📊 Model Evaluation</h1>
        <p className="text-slate-500 mt-1">
          XGBoost vs Random Forest — Weak Topic Predictor ({data.dataset_size} samples, {data.data_source})
        </p>
        {stats && (
          <p className="text-sm text-slate-400 mt-1">
            Trained on {stats.real_users_scraped} real LeetCode users (avg {stats.avg_problems_solved} problems solved) + synthetic data
          </p>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <MetricsCard name="XGBoost" metrics={data.xgboost} highlight={data.winner === 'XGBoost'} />
        <MetricsCard name="Random Forest" metrics={data.random_forest} highlight={data.winner === 'Random Forest'} />
      </div>

      <div className="bg-white rounded-xl p-6 border border-slate-200">
        <h2 className="font-bold text-xl mb-4">Per-Class F1 Score Comparison</h2>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={f1ChartData}>
            <XAxis dataKey="topic" />
            <YAxis domain={[0, 1]} />
            <Tooltip />
            <Legend />
            <Bar dataKey="XGBoost" fill="#3b82f6" />
            <Bar dataKey="Random Forest" fill="#f59e0b" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-white rounded-xl p-6 border border-slate-200 grid md:grid-cols-2 gap-8">
        <ConfusionMatrix matrix={data.xgboost.confusion_matrix} labels={data.class_labels} title="XGBoost Confusion Matrix" />
        <ConfusionMatrix matrix={data.random_forest.confusion_matrix} labels={data.class_labels} title="Random Forest Confusion Matrix" />
      </div>

      <div className="bg-white rounded-xl p-6 border border-slate-200">
        <h2 className="font-bold text-xl mb-4">Feature Importance ({data.winner})</h2>
        <div className="space-y-2">
          {Object.entries(data[winnerKey].feature_importance)
            .sort((a, b) => b[1] - a[1])
            .map(([feature, importance]) => (
              <div key={feature} className="flex items-center gap-2">
                <div className="w-40 text-sm">{feature}</div>
                <div className="flex-1 bg-slate-100 rounded-full h-4 overflow-hidden">
                  <div className="bg-blue-500 h-4 rounded-full" style={{ width: `${importance * 100}%` }}></div>
                </div>
                <div className="w-12 text-sm text-right">{(importance * 100).toFixed(1)}%</div>
              </div>
            ))}
        </div>
      </div>
    </div>
  )
}