import { BaseNode } from '@/interfaces/database/agent';
import { NodeProps, Position } from '@xyflow/react';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { NodeHandleId } from '../../constant';
import { CommonHandle } from './handle';
import { LeftHandleStyle, RightHandleStyle } from './handle-icon';
import NodeHeader from './node-header';
import { NodeWrapper } from './node-wrapper';

interface PowerRAGSplitterFormSchemaType {
  title_level?: number;
  chunk_token_num?: number;
  delimiter?: string;
  layout_recognize?: string;
}

function PowerRAGSplitterNode({
  id,
  data,
  isConnectable = true,
  selected,
}: NodeProps<BaseNode<PowerRAGSplitterFormSchemaType>>) {
  const { t } = useTranslation();

  const getNodeTitle = () => {
    switch (data.label) {
      case 'TitleBasedSplitter':
        return t('powerrag.nodes.titleBasedSplitter');
      default:
        return data.label;
    }
  };

  const getNodeDescription = () => {
    switch (data.label) {
      case 'TitleBasedSplitter':
        return t('powerrag.nodes.titleBasedSplitterDesc');
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

export default memo(PowerRAGSplitterNode);
