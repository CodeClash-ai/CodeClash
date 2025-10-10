import { useEffect, useState } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { api } from '../utils/api';
import type { SimWinsData } from '../types';
import './ScoresChart.css';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

interface ScoresChartProps {
  folderPath: string;
}

export function ScoresChart({ folderPath }: ScoresChartProps) {
  const [data, setData] = useState<SimWinsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, [folderPath]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const simWinsData = await api.getSimWinsAnalysis(folderPath);
      setData(simWinsData);
    } catch (err: any) {
      console.error('Failed to load sim wins data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="chart-loading">Loading scores chart...</div>;
  }

  if (error || !data || !data.players.length || !data.rounds.length) {
    return null; // Don't show anything if there's no data
  }

  // Generate colors for each player
  const colors = [
    'rgb(102, 126, 234)',
    'rgb(118, 75, 162)',
    'rgb(255, 99, 132)',
    'rgb(255, 159, 64)',
    'rgb(75, 192, 192)',
    'rgb(54, 162, 235)',
    'rgb(153, 102, 255)',
  ];

  const chartData = {
    labels: data.rounds,
    datasets: data.players.map((player, idx) => ({
      label: player,
      data: data.scores_by_player[player],
      borderColor: colors[idx % colors.length],
      backgroundColor: colors[idx % colors.length].replace('rgb', 'rgba').replace(')', ', 0.1)'),
      tension: 0.3,
      pointRadius: 4,
      pointHoverRadius: 6,
    })),
  };

  const options: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
        labels: {
          color: '#e0e0e0',
          font: {
            size: 12,
          },
        },
      },
      title: {
        display: true,
        text: 'Win Percentage Per Round',
        color: '#e0e0e0',
        font: {
          size: 16,
          weight: 'bold',
        },
      },
      tooltip: {
        callbacks: {
          label: (context) => {
            return `${context.dataset.label}: ${context.parsed.y.toFixed(1)}%`;
          },
        },
      },
    },
    scales: {
      x: {
        title: {
          display: true,
          text: 'Round',
          color: '#a0a0a0',
        },
        ticks: {
          color: '#a0a0a0',
        },
        grid: {
          color: 'rgba(255, 255, 255, 0.1)',
        },
      },
      y: {
        title: {
          display: true,
          text: 'Win Percentage (%)',
          color: '#a0a0a0',
        },
        ticks: {
          color: '#a0a0a0',
          callback: (value) => `${value}%`,
        },
        grid: {
          color: 'rgba(255, 255, 255, 0.1)',
        },
        min: 0,
        max: 100,
      },
    },
  };

  return (
    <div className="scores-chart-container">
      <div className="chart-wrapper">
        <Line data={chartData} options={options} />
      </div>
    </div>
  );
}
