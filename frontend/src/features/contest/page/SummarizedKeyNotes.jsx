"use client"

import React, { useEffect, useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import Header from "@/components/layout/Header"
import api from "@/services/api"
import { useSelector } from "react-redux"

function useQuery() {
  return new URLSearchParams(useLocation().search)
}

const SummarizedKeyNotes = () => {
  const query = useQuery()
  const contest_id = query.get("contest_id")
  const [summaries, setSummaries] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [contestMeta, setContestMeta] = useState(null)
  const navigate = useNavigate()
  const { user } = useSelector((state) => state.auth)
  const [regenerating, setRegenerating] = useState(false)

  useEffect(() => {
    if (!contest_id) return setError("Missing contest id")

    const fetchSummaries = async () => {
      try {
        const res = await api.get(`summarized-keynotes/?contest_id=${contest_id}`)
        setSummaries(res.data)
        try {
          const cm = await api.get(`contest/${contest_id}/`)
          setContestMeta(cm.data)
        } catch (e) {
          // ignore
        }
      } catch (err) {
        console.error(err)
        setError("Failed to load summaries")
      } finally {
        setLoading(false)
      }
    }

    fetchSummaries()
  }, [contest_id])

  const handleRegenerate = async () => {
    if (!contest_id) return
    setRegenerating(true)
    try {
      await api.post("summarized-keynotes/generate/", { contest_id })
      const res = await api.get(`summarized-keynotes/?contest_id=${contest_id}`)
      setSummaries(res.data)
    } catch (err) {
      console.error(err)
      setError("Failed to regenerate summaries")
    } finally {
      setRegenerating(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-blue-50 text-gray-900">
      <Header />
      <div className="max-w-7xl mx-auto px-8 py-10">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-10 border-b pb-5">
          <h1 className="text-4xl sm:text-5xl font-extrabold text-indigo-700 drop-shadow-md tracking-tight">
            📘 AI Summarized Key Notes
          </h1>
          <div className="flex items-center space-x-4 mt-4 sm:mt-0">
            {user && (user.role === "tutor" || user.is_staff) && (
              <button
                onClick={handleRegenerate}
                disabled={regenerating}
                className={`px-6 py-2 rounded-lg font-semibold text-white text-sm shadow-lg transition-all ${
                  regenerating
                    ? "bg-indigo-400 cursor-wait"
                    : "bg-gradient-to-r from-indigo-600 to-blue-500 hover:from-indigo-700 hover:to-blue-600"
                }`}
              >
                {regenerating ? "Regenerating..." : "🔁 Regenerate"}
              </button>
            )}
            <button
              onClick={() => navigate(-1)}
              className="px-4 py-2 text-indigo-600 font-medium border border-indigo-400 rounded-lg hover:bg-indigo-100 transition-all"
            >
              ← Back
            </button>
          </div>
        </div>

        {/* Contest Status */}
        <div className="bg-gradient-to-r from-indigo-100 to-blue-100 p-5 rounded-xl shadow-sm border-l-4 border-indigo-500 mb-8">
          <p className="text-lg font-medium text-gray-700">
            <span className="font-bold text-indigo-800 underline">Status:</span>{" "}
            <span className="font-semibold text-blue-700 uppercase">
              {contestMeta?.ai_summary_status || "pending"}
            </span>
          </p>
        </div>

        {loading && <p className="text-center text-gray-600 italic">Loading summaries...</p>}
        {error && <p className="text-red-500 text-center font-medium">{error}</p>}

        {!loading && !error && (
          <div className="space-y-10">
            {summaries.length === 0 && (
              <p className="text-center text-gray-600 bg-white p-6 rounded-xl shadow">
                No summaries available yet. They will be generated once results are published.
              </p>
            )}

            {summaries.map((s) => (
              <div
                key={s.id}
                className="bg-white p-8 rounded-2xl shadow-xl border border-gray-100 hover:shadow-2xl transition-transform hover:-translate-y-1"
              >
                {/* Question Section */}
                <div className="mb-6">
                  <h2 className="text-2xl sm:text-3xl font-bold text-indigo-700 underline decoration-indigo-400 mb-2">
                    🧩 Question
                  </h2>
                  <p className="text-gray-900 text-xl leading-relaxed font-semibold">
                    {s.question_text}
                  </p>
                </div>

                {/* Copy Button */}
                <div className="flex justify-end mb-4">
                  <CopyButton text={s.summary_text} />
                </div>

                {/* Divider */}
                <div className="border-t-2 border-dashed border-indigo-200 my-6"></div>

                {/* Key Notes Section */}
                <h3 className="text-2xl font-bold text-blue-700 underline mb-4">
                  💡 AI Key Note Summary
                </h3>
                <StructuredSummary text={s.summary_text} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default SummarizedKeyNotes

// --- Copy Button ---
function CopyButton({ text }) {
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text || "")
      alert("✅ Summary copied to clipboard!")
    } catch (e) {
      console.error("Copy failed", e)
    }
  }

  return (
    <button
      onClick={handleCopy}
      title="Copy summary"
      className="bg-gradient-to-r from-indigo-600 to-blue-500 hover:from-indigo-700 hover:to-blue-600 text-white text-sm px-4 py-2 rounded-lg shadow-md transition-all"
    >
      📋 Copy Summary
    </button>
  )
}

// --- Structured Summary Renderer ---
function StructuredSummary({ text }) {
  if (!text) return <div className="text-gray-500 italic">Not generated yet</div>

  const blocks = []
  const lines = text.split(/\r?\n/)
  let i = 0
  while (i < lines.length) {
    const line = lines[i].trimEnd()
    if (line.startsWith("```")) {
      const lang = line.slice(3).trim()
      i++
      const codeLines = []
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i])
        i++
      }
      i++
      blocks.push({ type: "code", lang, content: codeLines.join("\n") })
      continue
    }

    if (/^[-*]\s+/.test(line)) {
      const items = []
      while (i < lines.length && /^[-*]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*]\s+/, ""))
        i++
      }
      blocks.push({ type: "list", items })
      continue
    }

    if (
      /^#{1,6}\s+/.test(line) ||
      /^Answer:/.test(line) ||
      /^Explanation:/.test(line) ||
      /^Summary:/.test(line)
    ) {
      blocks.push({
        type: "heading",
        content: line.replace(/^#+\s*/, ""),
      })
      i++
      continue
    }

    const para = []
    while (i < lines.length && lines[i].trim() !== "") {
      para.push(lines[i])
      i++
    }
    if (para.length) {
      blocks.push({ type: "paragraph", content: para.join(" ").trim() })
    }

    while (i < lines.length && lines[i].trim() === "") i++
  }

  return (
    <div className="prose prose-lg max-w-none text-gray-800 leading-relaxed">
      {blocks.map((b, idx) => {
        if (b.type === "code")
          return (
            <pre
              key={idx}
              className="bg-gray-900 text-green-300 rounded-xl p-4 overflow-auto text-sm shadow-inner mb-4"
            >
              <code>{b.content}</code>
            </pre>
          )

        if (b.type === "list")
          return (
            <ul
              key={idx}
              className="list-disc list-inside mb-4 pl-5 text-gray-700 space-y-2"
            >
              {b.items.map((it, j) => (
                <li key={j}>
                  <span className="font-medium text-gray-800">{it}</span>
                </li>
              ))}
            </ul>
          )

        if (b.type === "heading")
          return (
            <h4
              key={idx}
              className="mt-6 mb-2 text-xl text-indigo-700 font-semibold underline decoration-indigo-400"
            >
              {b.content}
            </h4>
          )

        return (
          <p key={idx} className="mb-4 text-gray-900 font-medium">
            {b.content}
          </p>
        )
      })}
    </div>
  )
}
