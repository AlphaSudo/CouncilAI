import { BookOpen, Check, LoaderCircle, Minus, Users } from "lucide-react";
import type { Dict } from "./types";
import "./collective-research.css";

// Quiet shared workspace: parallel contributions first, one pooled library below.
// Progress becomes a compact disclosure after the common evidence barrier closes.
export function CollectiveResearch({
  value,
  explain,
  onSource,
}: {
  value?: Dict;
  explain: boolean;
  onSource: (version: string, start: number, end: number) => void;
}) {
  if (!value) return null;
  const active = !["ready", "limited"].includes(value.state);
  const members: Dict[] = value.members || [];
  const phases: Dict = {
    planning: "Choosing complementary queries",
    searching: "Searching the web in parallel",
    extracting: "Saving pages to the shared library",
    paused: "Research paused",
  };
  const content = (
    <>
      <p className="collective-purpose">
        Each model contributes research. All opening answers use the same shared
        sources.
      </p>
      <ul className="collective-members">
        {members.map((member) => (
          <li key={member.member_id}>
            <div>
              <strong>{member.name}</strong>
              <span>{member.angle}</span>
              {!["searched", "limited"].includes(member.state) && active ? (
                <LoaderCircle size={13} className="council-spin" />
              ) : member.results?.length ? (
                <Check size={13} />
              ) : (
                <Minus size={13} />
              )}
            </div>
            {member.query && <p>{member.query}</p>}
            <small>
              {member.search_finished
                ? `${member.results?.length || 0} results${member.reused ? " · cached" : ""}`
                : member.state === "planning"
                  ? "Planning a search"
                  : "Waiting for discovery"}
              {member.query_origin === "fallback"
                ? " · assigned-angle query"
                : member.query_origin === "model"
                  ? " · model-chosen query"
                  : ""}
              {member.query_adjusted_for_overlap
                ? " · angle added to avoid a duplicate query"
                : ""}
            </small>
            {explain && member.planning_limitation && (
              <p className="collective-limitation">
                {member.planning_limitation}
              </p>
            )}
            {member.search_limitation && (
              <p className="collective-limitation">
                {member.search_limitation}
              </p>
            )}
          </li>
        ))}
      </ul>
      {value.pages?.length > 0 && (
        <div className="collective-library">
          <strong>
            <BookOpen size={14} /> Shared library
          </strong>
          <ul>
            {value.pages.map((page: Dict) => (
              <li key={page.url}>
                <div>
                  {page.version_id ? (
                    <button
                      type="button"
                      onClick={() => onSource(page.version_id, 1, 1)}
                    >
                      {page.title || page.url}
                    </button>
                  ) : (
                    <a href={page.url} target="_blank" rel="noreferrer">
                      {page.title || page.url}
                    </a>
                  )}
                  <small>
                    {page.access === "extracted_page"
                      ? "Page saved"
                      : "Search excerpt"}
                  </small>
                </div>
                <small>
                  Found by{" "}
                  {page.contributors
                    .map(
                      (id: string) =>
                        members.find((m) => m.member_id === id)?.name || id,
                    )
                    .join(", ")}
                </small>
              </li>
            ))}
          </ul>
        </div>
      )}
      {value.extraction_limitation && (
        <p className="collective-limitation">
          {value.extraction_limitation}. Search excerpts remain available.
        </p>
      )}
      {explain && (
        <p className="collective-purpose">
          Research planning uses the existing request and spending allowances.
          Page retrieval is not factual verification. Opening answers are not
          shared during this phase.
        </p>
      )}
    </>
  );
  return (
    <section
      className="collective-research"
      aria-label="Collective web research"
      data-state={value.state}
    >
      {active ? (
        <>
          <header>
            <Users size={16} />
            <strong>Researching together</strong>
            <span>{phases[value.state] || "Building the shared library"}</span>
          </header>
          {content}
        </>
      ) : (
        <details>
          <summary>
            <Users size={16} />
            <strong>Shared research</strong>
            <span>
              {members.length} researchers · {value.extracted_pages || 0} pages
              saved{value.state === "limited" ? " · partial coverage" : ""}
            </span>
          </summary>
          {content}
        </details>
      )}
    </section>
  );
}
