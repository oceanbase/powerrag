import { BaseNode } from '@/interfaces/database/agent';
import { NodeProps, Position } from '@xyflow/react';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { NodeHandleId } from '../../constant';
import { CommonHandle } from './handle';
import { LeftHandleStyle, RightHandleStyle } from './handle-icon';
import NodeHeader from './node-header';
import { NodeWrapper } from './node-wrapper';

interface PowerRAGExtractorFormSchemaType {
  entity_types?: string[];
  use_regex?: boolean;
  use_llm?: boolean;
  min_length?: number;
  max_length?: number;
}

function PowerRAGExtractorNode({
  id,
  data,
  isConnectable = true,
  selected,
}: NodeProps<BaseNode<PowerRAGExtractorFormSchemaType>>) {
  const { t } = useTranslation();

  const getNodeTitle = () => {
    switch (data.label) {
      case 'EntityExtractor':
        return t('powerrag.nodes.entityExtractor');
      default:
        return data.label;
    }
  };

  const getNodeDescription = () => {
    switch (data.label) {
      case 'EntityExtractor':
        return t('powerrag.nodes.entityExtractorDesc');
      default:
        return '';
    }
  };

  return (
    <NodeWrapper selected={selected}>
      <CommonHandle
        id={NodeHandleId.End}
        type="target"
        position={Position.Left}
        isConnectable={isConnectable}
        style={LeftHandleStyle}
        nodeId={id}
      />
      <NodeHeader id={id} label={data.label} name={getNodeTitle()} />
      <CommonHandle
        id={NodeHandleId.Start}
        type="source"
        position={Position.Right}
        isConnectable={isConnectable}
        style={RightHandleStyle}
        nodeId={id}
      />
    </NodeWrapper>
  );
}

export default memo(PowerRAGExtractorNode);
