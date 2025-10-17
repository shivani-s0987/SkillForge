import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell } from 'recharts';

const StudentChart = ({ data }) => {
  const enrollData = (data.enrollments_over_time && data.enrollments_over_time.length) ? data.enrollments_over_time : Array.from({length:12}).map((_,i)=>({month:`M${i+1}`, count: Math.floor(Math.random()*20)}));
  const scoreTrend = (data.scores_trend && data.scores_trend.length) ? data.scores_trend : Array.from({length:8}).map((_,i)=>({name:`W${i+1}`, score: Math.floor(40+Math.random()*60)}));
  const pieData = [{name:'Completed', value: Math.random()*60+20},{name:'Ongoing', value: Math.random()*20+5},{name:'Not Started', value: Math.random()*20}];
  const COLORS = ['#7c3aed','#a78bfa','#c7d2fe'];

  return (
    <div className="space-y-6">
      <div style={{height:240}}>
        <ResponsiveContainer>
          <BarChart data={enrollData}>
            <XAxis dataKey="month" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="count" fill="#7c3aed" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div style={{height:200}} className="bg-white p-3 rounded">
          <ResponsiveContainer>
            <LineChart data={scoreTrend}>
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="score" stroke="#7c3aed" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div style={{height:200}} className="bg-white p-3 rounded flex items-center justify-center">
          <ResponsiveContainer>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" outerRadius={60} fill="#8884d8">
                {pieData.map((entry, idx)=> <Cell key={idx} fill={COLORS[idx%COLORS.length]} />)}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

export default StudentChart;
