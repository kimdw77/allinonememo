interface TagFilterProps {
  categories: string[];
  selected: string;
  onSelect: (category: string) => void;
}

export default function TagFilter({ categories, selected, onSelect }: TagFilterProps) {
  return (
    <div className="flex flex-wrap gap-2 mt-4">
      {/* 전체 버튼 */}
      <button
        onClick={() => onSelect("")}
        className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
          selected === ""
            ? "bg-indigo-500 text-white border-indigo-500"
            : "bg-white text-slate-600 border-slate-200 hover:border-indigo-300"
        }`}
      >
        전체
      </button>

      {categories.map((cat) => (
        <button
          key={cat}
          onClick={() => onSelect(cat === selected ? "" : cat)}
          className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
            selected === cat
              ? "bg-indigo-500 text-white border-indigo-500"
              : "bg-white text-slate-600 border-slate-200 hover:border-indigo-300"
          }`}
        >
          {cat}
        </button>
      ))}
    </div>
  );
}
