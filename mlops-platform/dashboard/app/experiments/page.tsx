import ExperimentsTable from "@/components/ExperimentsTable";
import { fetchExperiments } from "@/lib/api";

export default async function ExperimentsPage() {
  const runs = await fetchExperiments();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="text-lg font-semibold text-zinc-50">Experiments</div>
        <div className="mt-1 text-sm text-zinc-400">
          Browse MLflow runs and compare key metrics.
        </div>
      </div>
      <ExperimentsTable runs={runs} />
    </div>
  );
}
