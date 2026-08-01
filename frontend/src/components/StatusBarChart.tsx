import { useTheme } from '@mui/material/styles';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Box, Paper, Typography } from '@mui/material';
import { palette } from '../theme';

interface StatusBarChartProps {
  data: Record<string, number>;
}

const STATUS_ORDER = [
  'wishlist',
  'applied',
  'screen',
  'onsite',
  'offer',
  'rejected',
  'withdrawn',
];

const STATUS_LABELS: Record<string, string> = {
  wishlist: 'Wishlist',
  applied: 'Applied',
  screen: 'Screen',
  onsite: 'Onsite',
  offer: 'Offer',
  rejected: 'Rejected',
  withdrawn: 'Withdrawn',
};

const STATUS_COLORS: Record<string, string> = {
  wishlist: palette.statusGray,
  applied: palette.statusBlue,
  screen: palette.statusAmber,
  onsite: palette.statusBlue,
  offer: palette.statusGreen,
  rejected: palette.statusRed,
  withdrawn: palette.statusGray,
};

const LEGEND_ITEMS = [
  { label: 'Not started', color: palette.statusGray },
  { label: 'Active', color: palette.statusBlue },
  { label: 'In progress', color: palette.statusAmber },
  { label: 'Offer', color: palette.statusGreen },
  { label: 'Rejected', color: palette.statusRed },
];

export function StatusBarChart({ data }: StatusBarChartProps) {
  const theme = useTheme();

  const chartData = STATUS_ORDER.map((status) => ({
    status: STATUS_LABELS[status],
    rawStatus: status,
    count: data[status] ?? 0,
    color: STATUS_COLORS[status],
  }));

  const maxCount = Math.max(...chartData.map((d) => d.count), 1);

  return (
    <Paper
      elevation={0}
      sx={{
        p: 3,
        border: `1px solid ${palette.border}`,
        borderRadius: '10px',
        background: palette.surface,
      }}
    >
      <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '0.9375rem' }}>
        Applications by status
      </Typography>
      <Typography variant="body2" sx={{ color: palette.muted, fontSize: '0.78rem', mt: 0.25 }}>
        Where your {chartData.reduce((sum, d) => sum + d.count, 0)} applications currently sit.
      </Typography>

      <Box sx={{ height: 300, mt: 2.75 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            margin={{ top: 8, right: 8, left: -20, bottom: 8 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke={palette.border}
              vertical={false}
            />
            <XAxis
              dataKey="status"
              tick={{ fill: palette.muted, fontSize: 11.5, fontFamily: theme.typography.fontFamily }}
              axisLine={{ stroke: palette.border }}
              tickLine={false}
            />
            <YAxis
              allowDecimals={false}
              domain={[0, maxCount]}
              tick={{ fill: palette.muted2, fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              cursor={{ fill: 'rgba(15, 42, 67, 0.03)' }}
              contentStyle={{
                borderRadius: 8,
                border: `1px solid ${palette.border}`,
                boxShadow: '0 4px 16px rgba(0,0,0,0.06)',
                fontSize: 13,
              }}
            />
            <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={46}>
              <LabelList
                dataKey="count"
                position="top"
                className="num"
                fill={palette.ink}
                fontSize={12}
                fontWeight={600}
              />
              {chartData.map((entry) => (
                <Cell key={entry.rawStatus} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Box>

      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 2,
          mt: 2,
        }}
      >
        {LEGEND_ITEMS.map((item) => (
          <Box
            key={item.label}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.75,
            }}
          >
            <Box
              sx={{
                width: 9,
                height: 9,
                borderRadius: '2px',
                bgcolor: item.color,
              }}
            />
            <Typography
              variant="body2"
              sx={{ fontSize: '0.72rem', color: palette.muted }}
            >
              {item.label}
            </Typography>
          </Box>
        ))}
      </Box>
    </Paper>
  );
}
