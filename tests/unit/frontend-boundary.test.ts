import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SOURCE_ROOT = path.resolve(import.meta.dirname, "../../src");

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      return sourceFiles(fullPath);
    }
    return /\.(?:ts|tsx)$/.test(entry.name) ? [fullPath] : [];
  });
}

describe("frontend platform boundary", () => {
  it("does not bypass Anna Host APIs", () => {
    const forbidden = [
      { pattern: /\banna\s*\.\s*llm\b/, description: "direct anna.llm call" },
      { pattern: /\bfetch\s*\(/, description: "direct fetch call" },
      { pattern: /\bXMLHttpRequest\b/, description: "XMLHttpRequest" },
      { pattern: /\blocalStorage\b/, description: "localStorage" },
      { pattern: /\bsessionStorage\b/, description: "sessionStorage" },
      { pattern: /\bindexedDB\b/, description: "IndexedDB" },
    ];

    const violations = sourceFiles(SOURCE_ROOT).flatMap((file) => {
      const source = readFileSync(file, "utf8");
      return forbidden
        .filter(({ pattern }) => pattern.test(source))
        .map(
          ({ description }) =>
            `${path.relative(SOURCE_ROOT, file)}: ${description}`,
        );
    });

    expect(violations).toEqual([]);
  });
});
