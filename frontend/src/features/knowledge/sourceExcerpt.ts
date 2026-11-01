/** Group public excerpts for reflow without changing their wording or stored quotes. */
export function sourceExcerptBlocks(quote: string): string[] {
  const blocks: string[] = [];
  let lines: string[] = [];
  const flush = () => {
    if (lines.length) blocks.push(lines.join("\n"));
    lines = [];
  };
  for (const line of quote.replace(/\r\n?/g, "\n").split("\n")) {
    if (!line.trim()) {
      flush();
      continue;
    }
    const structuralLine = /^\s*(?:[•●▪‣–—*-]\s+|\d+[.)]\s+|#{1,6}\s+)/.test(line);
    const questionHeading = /\?\s*$/.test(line);
    const previous = lines.at(-1)?.trimEnd() ?? "";
    // PDF line endings within sentences reflow naturally inside each block.
    // Keep explicit paragraphs, list entries, question headings and completed prose apart.
    if (structuralLine || questionHeading || /[.!?:]["'’”)]?$/.test(previous)) flush();
    lines.push(line);
    if (questionHeading || /^\s*#{1,6}\s+/.test(line)) flush();
  }
  flush();
  return blocks;
}
