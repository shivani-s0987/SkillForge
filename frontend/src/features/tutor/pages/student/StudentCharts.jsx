import React from 'react';
import { RadialBarChart, RadialBar, Legend, ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, BarChart, Bar } from 'recharts';

const StudentCharts = ({ data }) => {
  const breakdown = data.performance?.breakdown || {completed:0, ongoing:0, not_started:0, total:1};
  const pieData = [
    { name: 'Completed', value: breakdown.completed },
    { name: 'Ongoing', value: breakdown.ongoing },
    { name: 'Not Started', value: breakdown.not_started }
  ];

  const scoreTrend = (data.contests && data.contests.length) ? data.contests.map((c,i)=>({name:`C${i+1}`, score: c.score || 0})) : [{name:'T1', score:50},{name:'T2', score:60}];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white p-4 rounded">
          <h4 className="mb-2 font-semibold">Course Completion Breakdown</h4>
          <div style={{height:200}}>
            <ResponsiveContainer>
              <RadialBarChart innerRadius="10%" outerRadius="80%" data={pieData} startAngle={180} endAngle={-180}>
                <RadialBar minAngle={15} label={{ position: 'inside' }} background clockWise dataKey="value" />
                <Legend />
              </RadialBarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white p-4 rounded">
          <h4 className="mb-2 font-semibold">Scores Trend</h4>
          <div style={{height:200}}>
            <ResponsiveContainer>
              <LineChart data={scoreTrend}>
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="score" stroke="#7c3aed" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="bg-white p-4 rounded">
        <h4 className="mb-2 font-semibold">Tests Distribution</h4>
        <div style={{height:200}}>
          <ResponsiveContainer>
            <BarChart data={scoreTrend}>
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="score" fill="#7c3aed" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

export default StudentCharts;
