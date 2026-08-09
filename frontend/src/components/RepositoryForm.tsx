import { useState, type FormEvent } from "react";

interface Props {
  onSubmit: (url: string) => void;
  submitting: boolean;
  error: string | null;
}

export function RepositoryForm({ onSubmit, submitting, error }: Props) {
  const [url, setUrl] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (url.trim()) onSubmit(url.trim());
  };

  return (
    <form className="repo-form" onSubmit={handleSubmit}>
      <input
        type="text"
        placeholder="https://github.com/owner/repository"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        disabled={submitting}
      />
      <button type="submit" disabled={submitting || !url.trim()}>
        {submitting ? "Analyzing…" : "Analyze repository"}
      </button>
      {error && <p className="form-error">{error}</p>}
    </form>
  );
}
