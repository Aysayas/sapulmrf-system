import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
export const TYPE_LABEL = {
    weighing_station: 'Weighing station',
    compost_sensor: 'Compost sensor',
    sorting_camera: 'Sorting camera',
};
export const useDevices = () => useQuery({ queryKey: ['devices'], queryFn: () => api('/devices'), refetchInterval: 30_000 });
function useDeviceMutation(fn) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: fn,
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['devices'] });
            qc.invalidateQueries({ queryKey: ['activity'] });
        },
    });
}
export const useRegisterDevice = () => useDeviceMutation((body) => api('/devices', { method: 'POST', body }));
export const useUpdateDevice = () => useDeviceMutation(({ id, ...body }) => api(`/devices/${id}`, { method: 'PATCH', body }));
export const useNewDeviceKey = () => useDeviceMutation((id) => api(`/devices/${id}/new-key`, { method: 'POST' }));
