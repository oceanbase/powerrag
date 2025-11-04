import { BaseNode } from '@/interfaces/database/agent';
import { NodeProps, Position } from '@xyflow/react';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { NodeHandleId } from '../../constant';
import { CommonHandle } from './handle';
import { LeftHandleStyle, RightHandleStyle } from './handle-icon';
import NodeHeader from './node-header';
import { NodeWrapper } from './node-wrapper';

interface PowerRAGParserFormSchemaType {
  formula_enable?: boolean;
  enable_ocr?: boolean;
  from_page?: number;
  to_page?: number;
  format_type?: string;
}

function PowerRAGParserNode({
  id,
  data,
  isConnectable = true,
  selected,
}: NodeProps<BaseNode<PowerRAGParserFormSchemaType>>) {
  const { t } = useTranslation();

  const getNodeTitle = () => {
    switch (data.label) {
      case 'PDFParser':
        return t('powerrag.nodes.pdfParser');
      case 'DocumentToPDF':
        return t('powerrag.nodes.documentToPdf');
      default:
        return data.label;
    }
  };

  const getNodeDescription = () => {
    switch (data.label) {
      case 'PDFParser':
        return t('powerrag.nodes.pdfParserDesc');
      case 'DocumentToPDF':
        return t('powerrag.nodes.documentToPdfDesc');
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

export default memo(PowerRAGParserNode);
