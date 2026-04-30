import { useState } from "react";

type RunPanelProps = {
  onStart: (payload: {
    parserInputPath?: string;
    rawText?: string;
    paperUrl?: string;
  }) => void;
  isStarting: boolean;
};

export function RunPanel({ onStart, isStarting }: RunPanelProps) {
  const [parserInputPath, setParserInputPath] = useState("");
  const [rawText, setRawText] = useState("");
  const [paperUrl, setPaperUrl] = useState("");

  return (
    <section className="panel">
      <h2>Run Controls</h2>
      <div className="controls">
        <label htmlFor="paper-url">Online paper URL (optional)</label>
        <input
          id="paper-url"
          value={paperUrl}
          onChange={(event) => setPaperUrl(event.target.value)}
          placeholder="https://arxiv.org/abs/... or a publisher PDF"
        />
        <label htmlFor="parser-input">Parser input path (optional)</label>
        <input
          id="parser-input"
          value={parserInputPath}
          onChange={(event) => setParserInputPath(event.target.value)}
          placeholder="data/input_paper.txt"
        />
        <label htmlFor="raw-text">Raw text (optional)</label>
        <textarea
          id="raw-text"
          value={rawText}
          onChange={(event) => setRawText(event.target.value)}
          placeholder="Paste the paper text here if not using a file path."
        />
        <button
          type="button"
          disabled={isStarting}
          onClick={() =>
            onStart({
              paperUrl: paperUrl || undefined,
              parserInputPath: parserInputPath || undefined,
              rawText: rawText || undefined,
            })
          }
        >
          {isStarting ? "Starting..." : "Start pipeline"}
        </button>
      </div>
    </section>
  );
}
