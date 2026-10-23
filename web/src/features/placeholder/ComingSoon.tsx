export default function ComingSoon({ title, phase }: { title: string; phase: number }) {
  return (
    <>
      <h1 className="text-2xl font-extrabold">{title}</h1>
      <div className="grid flex-1 place-items-center rounded-xl border border-dashed border-edge bg-white p-8 text-center text-ink-2">
        <div>
          <b className="block text-ink">Coming in Phase {phase}</b>
          This screen is designed in the prototype and gets built in a later phase of the roadmap.
        </div>
      </div>
    </>
  );
}
