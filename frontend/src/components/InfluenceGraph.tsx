import { useMemo } from 'react';
import ReactFlow, { Background, Controls, MarkerType } from 'reactflow';
import type { Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import type { DiscoveredRelationship } from '../types';

interface InfluenceGraphProps {
  correlations: DiscoveredRelationship[];
}

export default function InfluenceGraph({ correlations }: InfluenceGraphProps) {
  
  const { nodes, edges } = useMemo(() => {
    const defaultNodes: Node[] = [
      {
        id: 'Basis Weight',
        data: { label: 'Basis Weight' },
        position: { x: 400, y: 150 },
        className: 'bg-status-stable/10 text-status-stable border-2 border-status-stable/30 rounded-md px-6 py-3 font-semibold shadow-[inset_0_1px_0_rgba(255,255,255,0.05),0_4px_6px_-1px_rgba(0,0,0,0.4)]',
      }
    ];
    
    const defaultEdges: Edge[] = [];
    
    if (!correlations || correlations.length === 0) {
      return { nodes: defaultNodes, edges: defaultEdges };
    }

    // Create a dynamic node for every source parameter
    correlations.forEach((corr, index) => {
      const isAnomaly = corr.is_interaction;
      const nodeId = corr.source_parameter;
      
      // Position nodes in a semi-circle on the left
      const yOffset = (index - (correlations.length - 1) / 2) * 100;
      
      defaultNodes.push({
        id: nodeId,
        data: { 
          label: (
            <div className="flex flex-col items-center gap-1">
              <span>{corr.source_parameter}</span>
              {isAnomaly && (
                <span className="text-[0.55rem] uppercase tracking-wider text-accent bg-accent/10 px-1.5 py-0.5 rounded border border-accent/20">
                  Anomaly Discovered
                </span>
              )}
            </div>
          ) 
        },
        position: { x: 50, y: 150 + yOffset },
        className: `text-sm font-medium px-4 py-2 rounded-md border shadow-[inset_0_1px_0_rgba(255,255,255,0.05),0_4px_6px_-1px_rgba(0,0,0,0.4)] ${
          isAnomaly 
            ? 'bg-panel-elevated text-accent border-accent/50 shadow-accent/10' 
            : 'bg-panel-surface text-text-primary border-panel-border shadow-white/5'
        }`,
      });

      // Create connecting edge
      defaultEdges.push({
        id: `e-${nodeId}-bw`,
        source: nodeId,
        target: 'Basis Weight',
        animated: isAnomaly,
        label: `${corr.lag_seconds}s lag (r=${corr.strength.toFixed(2)})`,
        labelStyle: { fill: '#94a3b8', fontSize: 10, fontWeight: 500 },
        labelBgStyle: { fill: '#131821', fillOpacity: 0.8 },
        style: {
          strokeWidth: Math.max(1, Math.abs(corr.strength) * 5),
          stroke: isAnomaly ? '#f97316' : '#71717a',
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isAnomaly ? '#f97316' : '#71717a',
        },
      });
    });

    return { nodes: defaultNodes, edges: defaultEdges };
  }, [correlations]);

  return (
    <div className="w-full h-[400px] bg-panel-bg/30 rounded-xl border border-panel-border/50 overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        attributionPosition="bottom-right"
      >
        <Background color="#18181b" gap={16} />
        <Controls className="!bg-panel-surface !border-panel-border fill-text-primary rounded-md overflow-hidden" />
      </ReactFlow>
    </div>
  );
}
