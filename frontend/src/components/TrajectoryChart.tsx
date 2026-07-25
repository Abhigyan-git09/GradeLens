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
import type { TimeseriesPoint, TrajectoryPrediction, Recommendation } from '../types';
import { useMemo } from 'react';

interface TrajectoryChartProps {
  timeseries: TimeseriesPoint[];
  prediction?: TrajectoryPrediction | null;
  recommendation?: Recommendation | null;
}

export default function TrajectoryChart({
  timeseries,
  prediction,
  recommendation
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
          setpoint: lastPoint.setpoint,
          upperLimit: lastPoint.setpoint * 1.025,
          lowerLimit: lastPoint.setpoint * 0.975,
          forecast: h.predicted_bw,
          recommended: null
        });
      });
    }
    
    // If we have a recommendation that affects BW or just want to show stabilization trajectory
    if (recommendation && prediction && prediction.horizons.length > 0) {
      // Simple visual mock: recommended line converges to setpoint faster than forecast
      // We start at last actual point
      const futureDataPoints = data.filter(d => d.timestamp > lastPoint.timestamp);
      
      // Connect to last point
      lastPoint.recommended = lastPoint.actual;
      
      futureDataPoints.forEach((d, idx) => {
        // Linear convergence to setpoint for demonstration of "better trajectory"
        const progress = Math.min(1, (idx + 1) / futureDataPoints.length);
        const setpoint = d.setpoint;
        const currentDiff = lastPoint.actual - setpoint;
        // Recommended reduces diff faster
        d.recommended = setpoint + (currentDiff * (1 - progress * 1.5));
      });
    }
    
    return data;
  }, [timeseries, prediction, recommendation]);

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
          />
          <YAxis 
            domain={[minBw, maxBw]} 
            stroke="#64748b" 
            fontSize={10}
            tickFormatter={(val) => val.toFixed(1)}
            width={40}
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
            stroke="rgba(248,113,113,0.3)" 
            strokeWidth={1} 
            dot={false} 
            activeDot={false}
            isAnimationActive={false}
          />
          {/* Lower Limit Line */}
          <Line 
            type="monotone" 
            dataKey="lowerLimit" 
            stroke="rgba(248,113,113,0.3)" 
            strokeWidth={1} 
            dot={false} 
            activeDot={false}
            isAnimationActive={false}
          />

          {/* Setpoint Line */}
          <Line 
            type="stepAfter" 
            dataKey="setpoint" 
            stroke="#818cf8" 
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
            stroke="#60a5fa" 
            strokeWidth={2}
            strokeDasharray="3 3"
            dot={false} 
            isAnimationActive={true}
          />
          
          {/* Recommended Line */}
          {recommendation && (
            <Line 
              type="monotone" 
              dataKey="recommended" 
              stroke="#34d399" 
              strokeWidth={2}
              dot={false} 
              isAnimationActive={true}
            />
          )}

          {/* Actual Line (Drawn last to be on top) */}
          <Line 
            type="monotone" 
            dataKey="actual" 
            stroke="#e2e8f0" 
            strokeWidth={2.5} 
            dot={false} 
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
