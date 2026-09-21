import type { ReportOut } from "../api";

type GrammarFix = NonNullable<ReportOut["grammar_fixes"]>[number];

export function GrammarTable({ fixes }: { fixes: GrammarFix[] }) {
  if (fixes.length === 0) return null;

  return (
    <table className="w-full text-left text-sm">
      <thead>
        <tr className="text-muted-foreground">
          <th className="pb-2 pr-3 font-medium">Original</th>
          <th className="pb-2 pr-3 font-medium">Corrected</th>
          <th className="pb-2 font-medium">Why</th>
        </tr>
      </thead>
      <tbody>
        {fixes.map((fix, index) => (
          <tr key={index} className="border-t border-foreground/10">
            <td className="py-2 pr-3">{fix.original}</td>
            <td className="py-2 pr-3">{fix.corrected}</td>
            <td className="py-2 text-muted-foreground">{fix.explanation}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
