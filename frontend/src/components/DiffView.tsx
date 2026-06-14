interface Props {
  diff: string;
}

export function DiffView({ diff }: Props) {
  if (!diff.trim()) {
    return <div className="empty">No differences.</div>;
  }
  const lines = diff.split("\n");
  return (
    <div className="diff">
      {lines.map((line, i) => {
        let cls = "";
        if (line.startsWith("+") && !line.startsWith("+++")) cls = "add";
        else if (line.startsWith("-") && !line.startsWith("---")) cls = "del";
        else if (line.startsWith("@@")) cls = "hunk";
        return (
          <div key={i} className={cls}>
            {line || " "}
          </div>
        );
      })}
    </div>
  );
}
