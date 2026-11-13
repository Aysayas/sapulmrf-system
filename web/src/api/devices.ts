import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';

export type DeviceType = 'weighing_station' | 'compost_sensor' | 'sorting_camera';
export interface Device {
  id: number;
  code: string;
  type: DeviceType;
  location: string;
  active: boolean;
  last_seen_at: string | null;
  status: 'online' | 'offline' | 'never';
}
export type DeviceWithKey = Device & { key: string };

export const TYPE_LABEL: Record<DeviceType, string> = {
  weighing_station: 'Weighing station',
  compost_sensor: 'Compost sensor',
  sorting_camera: 'Sorting camera',
};

export const useDevices = () =>
  useQuery({ queryKey: ['devices'], queryFn: () => api<Device[]>('/devices'), refetchInterval: 30_000 });

function useDeviceMutation<T, R>(fn: (v: T) => Promise<R>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['devices'] });
      qc.invalidateQueries({ queryKey: ['activity'] });
    },
  });
}

export const useRegisterDevice = () =>
  useDeviceMutation((body: Pick<Device, 'code' | 'type' | 'location'>) => api<DeviceWithKey>('/devices', { method: 'POST', body }));

export const useUpdateDevice = () =>
  useDeviceMutation(({ id, ...body }: Partial<Pick<Device, 'code' | 'type' | 'location' | 'active'>> & { id: number }) =>
    api<Device>(`/devices/${id}`, { method: 'PATCH', body }),
  );

export const useNewDeviceKey = () => useDeviceMutation((id: number) => api<DeviceWithKey>(`/devices/${id}/new-key`, { method: 'POST' }));

/** What the kiosk camera sees right now (from the laptop's YOLO). */
export interface LiveDetection {
  category: string;
  recyclable: number;
  residual: number;
  bio: number;
  conf: number | null;
  progress?: number;
}
export interface LiveFeed {
  device_id: number;
  code: string;
  live: boolean;
  fps: number;
  w: number;
  h: number;
  det: LiveDetection | null;
  viewers: number;
  last_frame_at: string | null;
}

/** Live kiosk cameras. Polled every 2 s for status; the video itself is an MJPEG stream at liveUrl(). */
export const useLiveCameras = () =>
  useQuery({ queryKey: ['devices', 'live'], queryFn: () => api<LiveFeed[]>('/devices/live'), refetchInterval: 2_000 });

export const liveUrl = (deviceId: number, attempt = 0) => `/api/devices/${deviceId}/live.mjpg?a=${attempt}`;
