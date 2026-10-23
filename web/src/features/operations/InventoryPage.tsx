import { useInventory } from '../../api/operations';
import { FillBar } from '../../components/charts';
import { PageHeader } from '../../components/ui';
import { kg, Table, when } from './shared';

export default function InventoryPage() {
  const inv = useInventory();
  return (
    <>
      <PageHeader title="Inventory" sub="Sorted materials in storage, by storage area" />
      <section aria-label="Storage areas" className="grid grid-cols-2 gap-x-8 rounded-xl border border-line bg-white p-4">
        {inv.data?.areas.map((a) => <FillBar key={a.id} area={a} />)}
        {inv.data?.areas.length === 0 && <p className="text-sm text-ink-2">No storage areas yet. Add them in Settings › Master data.</p>}
      </section>
      <Table label="Stock" head={['Material', 'Storage area', 'Bags', 'Weight', 'Last change']}
        state={{ isPending: inv.isPending, error: inv.error, count: inv.data?.stock.length }} empty="Nothing in storage.">
        {inv.data?.stock.map((r) => (
          <tr key={`${r.material}|${r.area}`}>
            <td className="font-semibold">{r.material}</td>
            <td>{r.area}</td>
            <td>{r.bags}</td>
            <td>{kg(r.kg)}</td>
            <td className="whitespace-nowrap text-ink-2">{when(r.last_change)}</td>
          </tr>
        ))}
      </Table>
    </>
  );
}
