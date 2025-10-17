import React from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar } from 'recharts';
import { motion } from 'framer-motion';

const COLORS = ['#7c3aed', '#f97316', '#ef4444'];

const StudentContests = ({ contests, summary, time_series }) => {
  const lineData = (time_series && time_series.scores_trend) ? time_series.scores_trend.map(d => ({ date: new Date(d.date).toLocaleDateString(), score: d.score })) : [];
  const pieData = [
    { name: 'Present', value: time_series?.attendance_ratio?.present || 0 },
    { name: 'Absent', value: time_series?.attendance_ratio?.absent || 0 }
  ];

  return (
    <motion.div initial={{opacity:0, y:8}} animate={{opacity:1, y:0}} className="mt-6 bg-white p-4 rounded shadow">
      <h4 className="text-lg font-semibold text-indigo-700">Contests & Tests</h4>

      <div className="mt-3 grid grid-cols-1 md:grid-cols-5 gap-4">
        <div className="md:col-span-1 bg-indigo-50 p-3 rounded">
          <div className="text-sm text-gray-500">Total Tests</div>
          <div className="text-2xl font-bold text-indigo-600">{summary.total_tests}</div>
        </div>
        <div className="md:col-span-1 bg-indigo-50 p-3 rounded">
          <div className="text-sm text-gray-500">Attempted</div>
          <div className="text-2xl font-bold text-indigo-600">{summary.tests_attempted}</div>
        </div>
        <div className="md:col-span-1 bg-indigo-50 p-3 rounded">
          <div className="text-sm text-gray-500">Avg Score</div>
          <div className="text-2xl font-bold text-indigo-600">{summary.average_score}</div>
        </div>
        <div className="md:col-span-1 bg-indigo-50 p-3 rounded">
          <div className="text-sm text-gray-500">Attendance %</div>
          <div className="text-2xl font-bold text-indigo-600">{summary.attendance_percentage}%</div>
        </div>
        <div className="md:col-span-1 bg-indigo-50 p-3 rounded">
          <div className="text-sm text-gray-500">Best Score</div>
          <div className="text-2xl font-bold text-indigo-600">{summary.best?.score ?? '-'}</div>
          <div className="text-xs text-gray-500">{summary.best?.title ?? ''} {summary.best?.rank ? `• Rank ${summary.best.rank}` : ''}</div>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <div className="overflow-x-auto border rounded">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Title</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Date</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">Max Marks</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">Student Marks</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-gray-500">Attendance</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">Rank</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">Progress</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {contests.map((c) => (
                  <tr key={c.id} className={`${c.attendance_status === 'Absent' ? 'bg-gray-100 text-gray-400' : ''}`}>
                    <td className="px-4 py-3 text-sm">{c.title}</td>
                    <td className="px-4 py-3 text-sm">{new Date(c.date_conducted).toLocaleString()}</td>
                    <td className="px-4 py-3 text-sm text-right">{c.max_marks}</td>
                    <td className={`px-4 py-3 text-sm text-right ${c.attendance_status==='Absent' ? 'text-gray-400' : 'text-indigo-600'}`}>{c.student_marks}</td>
                    <td className="px-4 py-3 text-center"><span className={`px-2 py-1 rounded text-xs ${c.attendance_status==='Absent' ? 'bg-red-100 text-red-600' : 'bg-green-100 text-green-600'}`}>{c.attendance_status}</span></td>
                    <td className="px-4 py-3 text-sm text-right">{c.rank ?? '-'}</td>
                    <td className="px-4 py-3 text-sm text-right">{c.progress_percentage}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="space-y-4">
          <div className="p-3 bg-white rounded shadow">
            <h5 className="text-sm text-gray-500">Attendance Ratio</h5>
            <div style={{height:180}}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" outerRadius={60} fill="#8884d8">
                    {pieData.map((entry, idx) => <Cell key={idx} fill={COLORS[idx % COLORS.length]} />)}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="p-3 bg-white rounded shadow">
            <h5 className="text-sm text-gray-500">Score Trend</h5>
            <div style={{height:180}}>
              <ResponsiveContainer>
                <LineChart data={lineData}>
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Line type="monotone" dataKey="score" stroke="#7c3aed" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="p-3 bg-white rounded shadow">
            <h5 className="text-sm text-gray-500">Score Comparison</h5>
            <div style={{height:180}}>
              <ResponsiveContainer>
                <BarChart data={lineData}>
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="score" fill="#7c3aed" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export default StudentContests;
