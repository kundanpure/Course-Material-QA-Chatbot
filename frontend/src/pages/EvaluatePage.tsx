import React, { useState } from "react";
import { Send, Upload, Trophy, ChevronDown, ChevronUp } from "lucide-react";
import apiClient from "../services/api";
import MarkdownRenderer from "../components/MarkdownRenderer";

type Difficulty = "lenient" | "moderate" | "strict";

interface EvaluationResult {
  score: number;
  strengths: string[];
  missing_concepts: string[];
  improvements: string[];
  model_answer: string;
  grading_mode: string;
}

// ── Helper: extract text from PDF/DOCX in-browser via backend ─────────────────
async function extractTextFromFile(file: File): Promise<string> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiClient.post("/api/v1/extract-text", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data.text as string;
}

export default function EvaluatePage() {
  const [difficulty, setDifficulty] = useState<Difficulty>("moderate");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [extractingQuestion, setExtractingQuestion] = useState(false);
  const [extractingAnswer, setExtractingAnswer] = useState(false);
  const [result, setResult] = useState<EvaluationResult | null>(null);
  const [showModelAnswer, setShowModelAnswer] = useState(false);
  const [questionFile, setQuestionFile] = useState<File | null>(null);
  const [answerFile, setAnswerFile] = useState<File | null>(null);

  const isDisabled = !question.trim() || !answer.trim() || loading || extractingQuestion || extractingAnswer;

  // ── Question file upload: extract text → populate textarea ─────────────────
  const handleQuestionFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] || null;
    setQuestionFile(selected);
    if (!selected) return;

    try {
      setExtractingQuestion(true);
      const text = await extractTextFromFile(selected);
      setQuestion(text);
    } catch (err) {
      console.error("Failed to extract question text:", err);
      alert("Could not extract text from the question file. Please paste it manually.");
    } finally {
      setExtractingQuestion(false);
    }
  };

  // ── Answer file upload: extract text → populate textarea ───────────────────
  const handleAnswerFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] || null;
    setAnswerFile(selected);
    if (!selected) return;

    try {
      setExtractingAnswer(true);
      const text = await extractTextFromFile(selected);
      setAnswer(text);
    } catch (err) {
      console.error("Failed to extract answer text:", err);
      alert("Could not extract text from the answer file. Please paste it manually.");
    } finally {
      setExtractingAnswer(false);
    }
  };

  // ── Evaluate: send question + answer + optional reference file ─────────────
  const handleEvaluate = async () => {
    if (isDisabled) return;

    setLoading(true);
    setResult(null);

    try {
      let response;

      if (file) {
        // Send as multipart/form-data so the reference file travels with the request
        const formData = new FormData();
        formData.append("question", question);
        formData.append("student_answer", answer);
        formData.append("grading_mode", difficulty);
        formData.append("reference_file", file);

        response = await apiClient.post("/api/v1/evaluate/with-reference", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
      } else {
        // No reference file — plain JSON as before
        response = await apiClient.post("/api/v1/evaluate", {
          question,
          student_answer: answer,
          grading_mode: difficulty,
        });
      }

      setResult(response.data);
    } catch (err) {
      console.error("Evaluation error:", err);
      alert("Evaluation failed. Check backend.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto p-8 space-y-8">

      {/* 🟣 Title */}
      <div>
        <h1 className="text-3xl font-bold gradient-text">
          📝 Exam Answer Evaluation
        </h1>
        <p className="text-gray-500 dark:text-gray-400 mt-2">
          Evaluate your written answers with AI grading.
        </p>
      </div>

      {/* 🟵 Difficulty Selector */}
      <div className="space-y-2">
        <p className="font-semibold">Select Difficulty</p>
        <div className="flex space-x-3">
          {["lenient", "moderate", "strict"].map((mode) => (
            <button
              key={mode}
              onClick={() => setDifficulty(mode as Difficulty)}
              className={`px-4 py-2 rounded-full text-sm font-semibold transition-all
                ${
                  difficulty === mode
                    ? mode === "lenient"
                      ? "bg-green-500 text-white"
                      : mode === "moderate"
                      ? "bg-blue-500 text-white"
                      : "bg-red-500 text-white"
                    : "bg-gray-200 dark:bg-dark-700 text-gray-600 dark:text-gray-400"
                }`}
            >
              {mode.charAt(0).toUpperCase() + mode.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* 🟡 Question */}
      <div className="space-y-2">
        <label className="font-semibold">Exam Question</label>
        <label className="inline-flex items-center space-x-2 cursor-pointer bg-gray-100 dark:bg-dark-700 px-4 py-2 rounded-lg hover:bg-gray-200 dark:hover:bg-dark-600 w-fit">
          <Upload size={16} />
          <span className="text-sm">
            {extractingQuestion ? "Extracting..." : "Upload Question PDF/DOCX"}
          </span>
          <input
            type="file"
            accept=".pdf,.doc,.docx"
            hidden
            disabled={extractingQuestion}
            onChange={handleQuestionFileChange}
          />
        </label>

        {questionFile && !extractingQuestion && (
          <p className="text-sm text-green-600 dark:text-green-400">
            ✅ Extracted: {questionFile.name}
          </p>
        )}
        {extractingQuestion && (
          <p className="text-sm text-blue-500 animate-pulse">⏳ Extracting text from file...</p>
        )}

        <textarea
          rows={4}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          className="w-full p-4 rounded-xl border dark:border-dark-600 bg-white dark:bg-dark-800"
          placeholder="Enter the exam question or upload a file above..."
        />
      </div>

      {/* 🟠 Student Answer */}
      <div className="space-y-2">
        <label className="font-semibold">Your Answer</label>

        <label className="inline-flex items-center space-x-2 cursor-pointer bg-gray-100 dark:bg-dark-700 px-4 py-2 rounded-lg hover:bg-gray-200 dark:hover:bg-dark-600 w-fit">
          <Upload size={16} />
          <span className="text-sm">
            {extractingAnswer ? "Extracting..." : "Upload Answer PDF/DOCX"}
          </span>
          <input
            type="file"
            accept=".pdf,.doc,.docx"
            hidden
            disabled={extractingAnswer}
            onChange={handleAnswerFileChange}
          />
        </label>

        {answerFile && !extractingAnswer && (
          <p className="text-sm text-green-600 dark:text-green-400">
            ✅ Extracted: {answerFile.name}
          </p>
        )}
        {extractingAnswer && (
          <p className="text-sm text-blue-500 animate-pulse">⏳ Extracting text from file...</p>
        )}

        <textarea
          rows={8}
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          className="w-full p-4 rounded-xl border dark:border-dark-600 bg-white dark:bg-dark-800"
          placeholder="Write your answer here or upload a file above..."
        />
      </div>

      {/* 🟢 Reference Material */}
      <div className="space-y-2">
        <label className="font-semibold">
          📎 Attach Reference Material (optional)
        </label>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          If provided, the AI will grade the answer against this material.
        </p>
        <label className="inline-flex items-center space-x-2 cursor-pointer bg-gray-100 dark:bg-dark-700 px-4 py-2 rounded-lg hover:bg-gray-200 dark:hover:bg-dark-600">
          <Upload size={16} />
          <span>Upload PDF/DOCX</span>
          <input
            type="file"
            accept=".pdf,.doc,.docx"
            hidden
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </label>
        {file && (
          <p className="text-sm text-green-600 dark:text-green-400">
            📎 Attached: {file.name}
          </p>
        )}
      </div>

      {/* 🔵 Evaluate Button */}
      <button
        onClick={handleEvaluate}
        disabled={isDisabled}
        className="w-full bg-gradient-to-r from-primary-600 to-purple-600 text-white py-3 rounded-xl font-semibold flex justify-center items-center space-x-2 disabled:opacity-50"
      >
        <Send size={18} />
        <span>{loading ? "Evaluating..." : "🚀 Evaluate Answer"}</span>
      </button>

      {/* 📊 Results */}
      {result && (
        <div className="space-y-6">

          {/* 🏆 Score Card */}
          <div className="bg-white dark:bg-dark-800 p-6 rounded-2xl shadow-lg border dark:border-dark-700 text-center">
            <Trophy className="mx-auto mb-3 text-yellow-500" size={32} />
            <h2 className="text-2xl font-bold">
              Score: {result.score} / 10
            </h2>
            <p className="text-sm text-gray-500">
              Difficulty: {result.grading_mode}
            </p>
          </div>

          {/* 💪 Strengths */}
          <SectionCard title="💪 Strengths">
            <ul className="list-disc pl-5 space-y-1">
              {result.strengths.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </SectionCard>

          {/* ❌ Missing Concepts */}
          <SectionCard title="❌ Missing Concepts">
            <ul className="list-disc pl-5 space-y-1">
              {result.missing_concepts.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </SectionCard>

          {/* 📈 Improvements */}
          <SectionCard title="📈 Improvements">
            <ul className="list-disc pl-5 space-y-1">
              {result.improvements.map((imp, i) => (
                <li key={i}>{imp}</li>
              ))}
            </ul>
          </SectionCard>

          {/* 🧠 Ideal Answer */}
          <div className="bg-white dark:bg-dark-800 p-6 rounded-2xl shadow border dark:border-dark-700">
            <button
              onClick={() => setShowModelAnswer(!showModelAnswer)}
              className="flex items-center justify-between w-full font-semibold"
            >
              🧠 Ideal Answer
              {showModelAnswer ? <ChevronUp /> : <ChevronDown />}
            </button>

            {showModelAnswer && (
              <div className="mt-4 prose dark:prose-invert max-w-none">
                <MarkdownRenderer content={result.model_answer} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ───────────── Helper Component ───────────── */

function SectionCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white dark:bg-dark-800 p-6 rounded-2xl shadow border dark:border-dark-700">
      <h3 className="font-semibold mb-3">{title}</h3>
      {children}
    </div>
  );
}
