import React from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

function structuredObject(text: string): object | undefined {
  const candidate = text
    .trim()
    .replace(/^```(?:json)?\s*\n([\s\S]*?)\n```$/i, "$1");
  if (!/^[{[]/.test(candidate)) return;
  const parse = (value: string) => {
    const result = JSON.parse(value);
    return result !== null && typeof result === "object"
      ? (result as object)
      : undefined;
  };
  try {
    return parse(candidate);
  } catch {
    // Old models emitted TeX backslashes without JSON escaping. Presentation only.
    if (!candidate.includes("$") || !/\\[A-Za-z]{2,}/.test(candidate)) return;
    const escaped = candidate.replace(
      /(?<!\\)\\(?=[A-Za-z]{2,}\b|[%!,;:_(){}\[\] ])/g,
      "\\\\",
    );
    try {
      return parse(escaped);
    } catch {
      // Some flat replies also contain unescaped quotation marks inside values.
      // Read complete labelled lines, preserving every value and the raw original.
      const lines = candidate.split(/\r?\n/).map((line) => line.trim());
      if (lines[0] !== "{" || lines.at(-1) !== "}") return;
      const entries: [string, string][] = [];
      for (const line of lines.slice(1, -1)) {
        const match =
          /^"([A-Za-z_][A-Za-z_0-9 ]{0,79})"\s*:\s*"(.*)"\s*,?$/.exec(line);
        if (!match || entries.some(([key]) => key === match[1])) return;
        entries.push([match[1], match[2]]);
      }
      return entries.length ? Object.fromEntries(entries) : undefined;
    }
  }
}

function retainCurrency() {
  return (tree: any) => {
    const visit = (node: any) => {
      node.children?.forEach((child: any, index: number) => {
        if (
          child.type === "inlineMath" &&
          /^\d[\d.,]*\s+(?:and|or|versus|remaining|to)\s*$/i.test(child.value)
        ) {
          node.children[index] = { type: "text", value: `$${child.value}$` };
        } else visit(child);
      });
    };
    visit(tree);
  };
}

// Presentation only: never change stored text, source offsets, or export hashes.
export function mathDelimiters(text: string): string {
  const formula = (s: string) => s.replace(/(?<!\\)%/g, "\\%");
  const nakedMath = (s: string) => {
    let result = "";
    for (let i = 0; i < s.length; i++) {
      const open = s[i],
        close = open === "[" ? "]" : ")";
      if ((open !== "(" && open !== "[") || s[i - 1] === "\\") {
        result += open;
        continue;
      }
      let depth = 1,
        end = i + 1;
      for (; end < Math.min(s.length, i + 4000) && s[end] !== "\n"; end++) {
        if (s[end] === open) depth++;
        if (s[end] === close) {
          depth--;
          if (depth === 0) break;
        }
      }
      const body = s.slice(i + 1, end);
      const knownTex =
        /^\s*\\(?:frac|dot|Delta|Omega|int|eta|sum|mu|Phi|nu|alpha|epsilon|varepsilon)\b/.test(
          body,
        );
      if (
        depth === 0 &&
        knownTex &&
        (open !== "[" ||
          (body.startsWith(" ") && body.endsWith(" ") && s[end + 1] !== "("))
      ) {
        result +=
          open === "["
            ? `\n\n$$\n${formula(body)}\n$$\n\n`
            : `$${formula(body)}$`;
        i = end;
      } else result += open;
    }
    return result;
  };
  const prose = (s: string) =>
    s
      .replace(/\\\[([\s\S]*?)\\\]/g, (_, s) => `\n\n$$\n${formula(s)}\n$$\n\n`)
      .replace(/\\\(([\s\S]*?)\\\)/g, (_, s) => `$${formula(s)}$`)
      // Existing formulas are protected before recognizing legacy bare delimiters.
      .split(/(\$\$[\s\S]*?\$\$|(?<!\\)\$(?!\$)(?:\\[\s\S]|[^$\\\n])*?\$)/g)
      .map((part, i) => (i % 2 ? formula(part) : nakedMath(part)))
      .join("");
  // Preserve fenced and inline code verbatim, including dollar signs and slashes.
  return text
    .split(/(`{3,}[\s\S]*?`{3,}|~{3,}[\s\S]*?~{3,}|`+[^`\n]*`+)/g)
    .map((part, i) => (i % 2 ? part : prose(part)))
    .join("");
}

type SourceHandler = (versionId: string, start: number, end: number) => void;
function Prose({ text, onSource }: { text: string; onSource?: SourceHandler }) {
  return (
    <Markdown
      remarkPlugins={[
        remarkGfm,
        [remarkMath, { singleDollarTextMath: true }],
        retainCurrency,
      ]}
      rehypePlugins={[
        [
          rehypeKatex,
          {
            trust: false,
            throwOnError: false,
            strict: "ignore",
            maxExpand: 200,
            maxSize: 20,
          },
        ],
      ]}
      skipHtml
      components={{
        pre: ({ children }) => {
          const child = React.Children.toArray(children)[0];
          if (
            React.isValidElement<{
              className?: string;
              children?: React.ReactNode;
            }>(child) &&
            child.props.className === "language-json"
          ) {
            const raw = String(child.props.children || "");
            const value = structuredObject(raw);
            if (value)
              return (
                <>
                  <Structured value={value} />
                  <details className="council-original">
                    <summary>Original structured response</summary>
                    <pre>{raw}</pre>
                  </details>
                </>
              );
          }
          return <pre>{children}</pre>;
        },
        img: ({ alt }) => <span>{alt || "Image omitted"}</span>,
        a: ({ href, children }) =>
          href?.startsWith("#saved-source:") && onSource ? (
            <button
              type="button"
              className="source-citation"
              onClick={() => {
                const match =
                  /^#saved-source:(version_[a-f0-9]{24}):(\d+):(\d+)$/.exec(
                    href,
                  );
                if (match)
                  onSource(match[1], Number(match[2]), Number(match[3]));
              }}
            >
              {children}
            </button>
          ) : (
            <a href={href} target="_blank" rel="noreferrer noopener">
              {children}
            </a>
          ),
      }}
    >
      {mathDelimiters(text).replace(
        /\[source:(version_[a-f0-9]{24}):L(\d+)-L(\d+)\]/g,
        "[Saved source · lines $2–$3](#saved-source:$1:$2:$3)",
      )}
    </Markdown>
  );
}

function Structured({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (typeof value === "string") return <Prose text={value} />;
  if (value === null || typeof value !== "object")
    return <p>{String(value)}</p>;
  if (depth > 10) return <pre>{JSON.stringify(value, null, 2)}</pre>;
  if (Array.isArray(value))
    return (
      <ol>
        {value.map((item, i) => (
          <li key={i}>
            <Structured value={item} depth={depth + 1} />
          </li>
        ))}
      </ol>
    );
  return (
    <div className="council-structured">
      {Object.entries(value).map(([key, item]) => (
        <section key={key}>
          <h4>{key.replace(/_/g, " ").replace(/([a-z])([A-Z])/g, "$1 $2")}</h4>
          <Structured value={item} depth={depth + 1} />
        </section>
      ))}
    </div>
  );
}

// Saved Markdown/KaTeX is immutable between content updates. Progress snapshots,
// elapsed timers and composer typing must not reparse every earlier response.
export const CouncilBody = React.memo(function CouncilBody({
  text,
  onSource,
}: {
  text: string;
  onSource?: SourceHandler;
}) {
  const parsed = structuredObject(text);
  if (parsed)
    return (
      <>
        <Structured value={parsed} />
        <details className="council-original">
          <summary>Original structured response</summary>
          <pre>{text}</pre>
        </details>
      </>
    );
  return <Prose text={text} onSource={onSource} />;
});
