import { useMemo } from 'react';
import ReactFlow, { Background, Controls, MarkerType } from 'reactflow';
import type { Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import type { DiscoveredRelationship } from '../types';

interface InfluenceGraphProps {
  correlations: DiscoveredRelationship[];
}

function RelationshipBadge({ label, type }: { label: string; type: 'known' | 'discovered' }) {
  return (
    <span className={`text-[0.55rem] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded border ${
      type === 'discovered'
        ? 'text-accent bg-accent/10 border-accent/30'
        : 'text-text-muted bg-panel-elevated border-panel-border'
    }`}>
      {label}
    </span>
  );
}

export default function InfluenceGraph({ correlations }: InfluenceGraphProps) {
  
  const { nodes, edges } = useMemo(() => {
    const defaultNodes: Node[] = [
      {
        id: 'Basis Weight',
        data: { 
          label: (
            <div className="flex flex-col items-center gap-1">
              <span className="text-sm font-bold">Basis Weight</span>
              <span className="text-[0.55rem] text-text-muted uppercase tracking-wider">Target Variable</span>
            </div>
          ) 
        },
        position: { x: 420, y: 150 },
        className: 'bg-status-stable/10 text-status-stable border-2 border-status-stable/30 rounded-lg px-6 py-4 font-semibold shadow-[inset_0_1px_0_rgba(255,255,255,0.05),0_4px_6px_-1px_rgba(0,0,0,0.4)]',
      }
    ];
    
    const defaultEdges: Edge[] = [];
    
    if (!correlations || correlations.length === 0) {
      return { nodes: defaultNodes, edges: defaultEdges };
    }

    correlations.forEach((corr, index) => {
      const isAnomaly = corr.is_interaction;
      const nodeId = corr.source_parameter;
      
      const yOffset = (index - (correlations.length - 1) / 2) * 110;
      
      defaultNodes.push({
        id: nodeId,
        data: { 
          label: (
            <div className="flex flex-col items-center gap-1.5 min-w-[120px]">
              <span className="text-xs font-semibold text-center leading-tight">{corr.source_parameter}</span>
              <RelationshipBadge 
                label={isAnomaly ? 'Newly Discovered' : 'Known Physics'} 
                type={isAnomaly ? 'discovered' : 'known'} 
              />
              <span className="text-[0.6rem] text-text-muted">
                Lag: {corr.lag_seconds}s | r = {corr.strength.toFixed(2)}
              </span>
            </div>
          ) 
        },
        position: { x: 30, y: 150 + yOffset },
        className: `text-sm font-medium px-3 py-2.5 rounded-lg border shadow-[inset_0_1px_0_rgba(255,255,255,0.05),0_4px_6px_-1px_rgba(0,0,0,0.4)] ${
          isAnomaly 
            ? 'bg-accent/5 text-accent border-accent/30' 
            : 'bg-panel-surface text-text-primary border-panel-border'
        }`,
      });

      defaultEdges.push({
        id: `e-${nodeId}-bw`,
        source: nodeId,
        target: 'Basis Weight',
        animated: isAnomaly,
        label: isAnomaly ? '⚠ Anomalous coupling detected' : 'Standard control loop',
        labelStyle: { fill: isAnomaly ? '#f97316' : '#94a3b8', fontSize: 9, fontWeight: 600 },
        labelBgStyle: { fill: '#131821', fillOpacity: 0.9 },
        style: {
          strokeWidth: Math.max(1.5, Math.abs(corr.strength) * 4),
          stroke: isAnomaly ? '#f97316' : '#52525b',
          strokeDasharray: isAnomaly ? '4 3' : 'none',
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isAnomaly ? '#f97316' : '#52525b',
          width: 12,
          height: 12,
        },
      });
    });

    return { nodes: defaultNodes, edges: defaultEdges };
  }, [correlations]);

  return (
    <div className="w-full h-[380px] bg-panel-bg/30 rounded-xl border border-panel-border/50 overflow-hidden relative">
      {correlations.length === 0 ? (
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="text-sm text-text-muted">No significant relationships detected for this event</p>
        </div>
      ) : (
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          attributionPosition="bottom-right"
          nodesDraggable={false}
          nodesConnectable={false}
        >
          <Background color="#18181b" gap={16} />
          <Controls className="!bg-panel-surface !border-panel-border fill-text-primary rounded-md overflow-hidden" />
        </ReactFlow>
      )}
      {correlations.length > 0 && (
        <div className="absolute bottom-3 left-3 flex items-center gap-3 text-[0.6rem] text-text-muted bg-panel-surface/80 backdrop-blur-sm px-2.5 py-1.5 rounded border border-panel-border/50">
          <span className="flex items-center gap-1">
            <span className="w-3 h-0.5 bg-[#52525b] inline-block" /> Known relationship
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-0.5 bg-accent inline-block" style={{ borderTop: '1.5px dashed #f97316', height: 0 }} /> Newly discovered
          </span>
          <span className="text-text-muted/60">|</span>
          <span>Arrows show direction of influence → Basis Weight</span>
        </div>
      )}
    </div>
  );
}
