import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceArea
} from 'recharts';
import type { TimeseriesPoint, TrajectoryPrediction } from '../types';
import { useMemo } from 'react';

interface TrajectoryChartProps {
  timeseries: TimeseriesPoint[];
  prediction?: TrajectoryPrediction | null;
  counterfactual?: TrajectoryPrediction | null;
}

export default function TrajectoryChart({
  timeseries,
  prediction,
  counterfactual
}: TrajectoryChartProps) {
  
  const chartData = useMemo(() => {
    if (!timeseries || timeseries.length === 0) return [];
    
    // Base data from actuals
    const data = timeseries.map(pt => {
      const date = new Date(pt.timestamp);
      return {
        time: date.toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' }),
        timestamp: date.getTime(),
        actual: pt.basis_weight_actual,
        setpoint: pt.basis_weight_setpoint,
        upperLimit: pt.basis_weight_setpoint * 1.025,
        lowerLimit: pt.basis_weight_setpoint * 0.975,
        forecast: null as number | null,
        recommended: null as number | null
      };
    });
    
    const lastPoint = data[data.length - 1];
    
    // If we have predictions, append them into the future
    if (prediction && prediction.horizons.length > 0) {
      // Connect forecast line from last actual
      lastPoint.forecast = lastPoint.actual;
      
      prediction.horizons.forEach(h => {
        const futureTime = new Date(lastPoint.timestamp + h.seconds * 1000);
        data.push({
          time: futureTime.toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' }),
          timestamp: futureTime.getTime(),
          actual: null as any,
          setpoint: h.predicted_setpoint,
          upperLimit: h.predicted_setpoint * 1.025,
          lowerLimit: h.predicted_setpoint * 0.975,
          forecast: h.predicted_bw,
          recommended: null
        });
      });
    }
    
    if (counterfactual && prediction && prediction.horizons.length > 0) {
      lastPoint.recommended = lastPoint.actual;
      const byHorizon = new Map(
        counterfactual.horizons.map(horizon => [
          horizon.seconds,
          horizon.predicted_bw,
        ])
      );
      data
        .filter(d => d.timestamp > lastPoint.timestamp)
        .forEach(d => {
          const seconds = Math.round((d.timestamp - lastPoint.timestamp) / 1000);
          d.recommended = byHorizon.get(seconds) ?? null;
      });
    }
    
    return data;
  }, [timeseries, prediction, counterfactual]);

  if (!chartData || chartData.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center relative overflow-hidden rounded-lg bg-panel-bg/50 border border-panel-border/30">
         <p className="text-text-muted text-sm">Loading telemetry data...</p>
      </div>
    );
  }

  const minBw = Math.min(...chartData.map(d => d.lowerLimit)) * 0.95;
  const maxBw = Math.max(...chartData.map(d => d.upperLimit)) * 1.05;

  return (
    <div className="flex-1 relative overflow-hidden rounded-lg bg-panel-bg/30">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 20, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(226,232,240,0.08)" vertical={false} />
          <XAxis 
            dataKey="time" 
            stroke="#64748b" 
            fontSize={10}
            tickMargin={10}
            minTickGap={30}
            label={{ value: "Time (HH:MM:SS)", position: "insideBottom", offset: -8, fill: "#94a3b8", fontSize: 10 }}
          />
          <YAxis 
            domain={[minBw, maxBw]} 
            stroke="#64748b" 
            fontSize={10}
            tickFormatter={(val) => val.toFixed(1)}
            width={60}
            label={{ value: "Basis Weight (g/m²)", angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 10, style: { textAnchor: 'middle' } }}
          />
          
          <Tooltip 
            contentStyle={{ backgroundColor: '#131821', border: '1px solid #1f2937', borderRadius: '8px', fontSize: '12px' }}
            itemStyle={{ color: '#e2e8f0' }}
          />

          {/* Acceptable Limits Area */}
          <ReferenceArea 
            y1={chartData[0]?.lowerLimit} 
            y2={chartData[0]?.upperLimit} 
            fill="rgba(255,255,255,0.02)" 
          />
          
          {/* Upper Limit Line */}
          <Line 
            type="monotone" 
            dataKey="upperLimit" 
            stroke="var(--color-chart-limit-line, rgba(239, 68, 68, 0.45))" 
            strokeWidth={1} 
            dot={false} 
            activeDot={false}
            isAnimationActive={false}
          />
          {/* Lower Limit Line */}
          <Line 
            type="monotone" 
            dataKey="lowerLimit" 
            stroke="var(--color-chart-limit-line, rgba(239, 68, 68, 0.45))" 
            strokeWidth={1} 
            dot={false} 
            activeDot={false}
            isAnimationActive={false}
          />

          {/* Setpoint Line */}
          <Line 
            type="stepAfter" 
            dataKey="setpoint" 
            stroke="var(--color-chart-setpoint, #a1a1aa)" 
            strokeWidth={1.5}
            strokeDasharray="4 4"
            dot={false} 
            activeDot={false}
            isAnimationActive={false}
          />

          {/* Forecast Line */}
          <Line 
            type="monotone" 
            dataKey="forecast" 
            stroke="var(--color-chart-forecast, #3b82f6)" 
            strokeWidth={2}
            strokeDasharray="6 4"
            dot={false} 
            isAnimationActive={true}
          />
          
          {/* Recommended Line */}
          {counterfactual && (
            <Line 
              type="monotone" 
              dataKey="recommended" 
              stroke="var(--color-chart-recommended, #f97316)" 
              strokeWidth={2.5}
              strokeDasharray="6 4"
              dot={false} 
              isAnimationActive={true}
            />
          )}

          {/* Actual Line (Drawn last to be on top) */}
          <Line 
            type="monotone" 
            dataKey="actual" 
            stroke="var(--color-chart-actual, #f4f4f5)" 
            strokeWidth={2.5} 
            dot={false} 
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
