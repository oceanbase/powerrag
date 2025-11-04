import { DataFlowSelect } from '@/components/data-pipeline-select';
import GraphRagItems from '@/components/parse-configuration/graph-rag-form-fields';
import RaptorFormFields from '@/components/parse-configuration/raptor-form-fields';
import { Button } from '@/components/ui/button';
import Divider from '@/components/ui/divider';
import { Form } from '@/components/ui/form';
import { FormLayout } from '@/constants/form';
import { DocumentParserType } from '@/constants/knowledge';
import { PermissionRole } from '@/constants/permission';
import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useState } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';
import { TopTitle } from '../dataset-title';
import {
  GenerateType,
  IGenerateLogButtonProps,
} from '../dataset/generate-button/generate';
import { ChunkMethodForm } from './chunk-method-form';
import ChunkMethodLearnMore from './chunk-method-learn-more';
import { MainContainer } from './configuration-form-container';
import { ChunkMethodItem, ParseTypeItem } from './configuration/common-item';
import { formSchema } from './form-schema';
import { GeneralForm } from './general-form';
import { useFetchKnowledgeConfigurationOnMount } from './hooks';
import { SavingButton } from './saving-button';
const enum DocumentType {
  DeepDOC = 'DeepDOC',
  PlainText = 'Plain Text',
}

const initialEntityTypes = [
  'organization',
  'person',
  'geo',
  'event',
  'category',
];

const enum MethodValue {
  General = 'general',
  Light = 'light',
}

export default function DatasetSettings() {
  const { t } = useTranslation();

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      parser_id: DocumentParserType.Naive,
      permission: PermissionRole.Me,
      parser_config: {
        layout_recognize: DocumentType.DeepDOC,
        chunk_token_num: 512,
        min_chunk_tokens: 64,
        delimiter: `\n`,
        auto_keywords: 0,
        auto_questions: 0,
        html4excel: false,
        topn_tags: 3,
        toc_extraction: false,
        raptor: {
          use_raptor: true,
          max_token: 256,
          threshold: 0.1,
          max_cluster: 64,
          random_seed: 0,
          prompt: t('knowledgeConfiguration.promptText'),
        },
        graphrag: {
          use_graphrag: true,
          entity_types: initialEntityTypes,
          method: MethodValue.Light,
        },
      },
      pipeline_id: '',
      parseType: 1,
      pagerank: 0,
    },
  });
  const knowledgeDetails = useFetchKnowledgeConfigurationOnMount(form);
  // const [pipelineData, setPipelineData] = useState<IDataPipelineNodeProps>();
  const [graphRagGenerateData, setGraphRagGenerateData] =
    useState<IGenerateLogButtonProps>();
  const [raptorGenerateData, setRaptorGenerateData] =
    useState<IGenerateLogButtonProps>();
  const [isDataLoaded, setIsDataLoaded] = useState(false);
  const [previousParserId, setPreviousParserId] = useState<string>('');

  useEffect(() => {
    console.log('🚀 ~ DatasetSettings ~ knowledgeDetails:', knowledgeDetails);
    if (knowledgeDetails) {
      // const data: IDataPipelineNodeProps = {
      //   id: knowledgeDetails.pipeline_id,
      //   name: knowledgeDetails.pipeline_name,
      //   avatar: knowledgeDetails.pipeline_avatar,
      //   linked: true,
      // };
      // setPipelineData(data);
      setGraphRagGenerateData({
        finish_at: knowledgeDetails.graphrag_task_finish_at,
        task_id: knowledgeDetails.graphrag_task_id,
      } as IGenerateLogButtonProps);
      setRaptorGenerateData({
        finish_at: knowledgeDetails.raptor_task_finish_at,
        task_id: knowledgeDetails.raptor_task_id,
      } as IGenerateLogButtonProps);
      form.setValue('parseType', knowledgeDetails.pipeline_id ? 2 : 1);
      form.setValue('pipeline_id', knowledgeDetails.pipeline_id || '');
      // Set previousParserId BEFORE isDataLoaded to ensure correct order
      setPreviousParserId(knowledgeDetails.parser_id || '');
      setIsDataLoaded(true);
      console.log('📌 Set previousParserId to:', knowledgeDetails.parser_id);
    }
  }, [knowledgeDetails, form]);

  async function onSubmit(data: z.infer<typeof formSchema>) {
    try {
      console.log('Form validation passed, submit data', data);
    } catch (error) {
      console.error('An error occurred during submission:', error);
    }
  }
  // const handleLinkOrEditSubmit = (
  //   data: IDataPipelineSelectNode | undefined,
  // ) => {
  //   console.log('🚀 ~ DatasetSettings ~ data:', data);
  //   if (data) {
  //     setPipelineData(data);
  //     form.setValue('pipeline_id', data.id || '');
  //     // form.setValue('pipeline_name', data.name || '');
  //     // form.setValue('pipeline_avatar', data.avatar || '');
  //   }
  // };

  const handleDeletePipelineTask = (type: GenerateType) => {
    if (type === GenerateType.KnowledgeGraph) {
      setGraphRagGenerateData({
        finish_at: '',
        task_id: '',
      } as IGenerateLogButtonProps);
    } else if (type === GenerateType.Raptor) {
      setRaptorGenerateData({
        finish_at: '',
        task_id: '',
      } as IGenerateLogButtonProps);
    }
  };

  const parseType = useWatch({
    control: form.control,
    name: 'parseType',
    defaultValue: knowledgeDetails.pipeline_id ? 2 : 1,
  });
  const selectedTag = useWatch({
    name: 'parser_id',
    control: form.control,
  });
  useEffect(() => {
    if (parseType === 1) {
      form.setValue('pipeline_id', '');
    }
    console.log('parseType', parseType);
  }, [parseType, form]);

  // Set default values when Title or Regex parser is selected (only when switching from another parser)
  useEffect(() => {
    if (!isDataLoaded) {
      return;
    }

    if (selectedTag === DocumentParserType.Title) {
      // Only set defaults when switching TO Title parser from another parser
      // This preserves saved values when loading existing Title configuration
      // IMPORTANT: Only set defaults if we're switching FROM a different parser
      // If previousParserId is empty or same as current, it means we're loading existing config
      if (
        previousParserId &&
        previousParserId !== '' &&
        previousParserId !== DocumentParserType.Title
      ) {
        const currentLayoutRecognize = form.getValues(
          'parser_config.layout_recognize',
        );
        const currentDelimiter = form.getValues('parser_config.delimiter');
        const currentTitleLevel = form.getValues('parser_config.title_level');

        console.log('🔄 Setting defaults for Title parser switch:', {
          previousParserId,
          currentLayoutRecognize,
          currentDelimiter,
          currentTitleLevel,
        });

        // Only set defaults if values are not already set
        if (!currentLayoutRecognize) {
          form.setValue('parser_config.layout_recognize', 'mineru');
        }
        if (!currentDelimiter) {
          form.setValue('parser_config.delimiter', '\n');
        }
        // IMPORTANT: Don't override title_level if it already has a value (from backend)
        if (currentTitleLevel === undefined || currentTitleLevel === null) {
          form.setValue('parser_config.title_level', 3);
        } else {
          console.log('✅ Preserving existing title_level:', currentTitleLevel);
        }
      } else {
        // Loading existing Title configuration - preserve all values
        const currentTitleLevel = form.getValues('parser_config.title_level');
        console.log(
          '📋 Loading existing Title config, title_level:',
          currentTitleLevel,
        );
      }

      // Update previous parser ID
      if (selectedTag !== previousParserId) {
        setPreviousParserId(selectedTag);
      }
    } else if (selectedTag === DocumentParserType.Regex) {
      // Set default regex_pattern and delimiter for Regex parser when switching from another parser
      if (
        previousParserId &&
        previousParserId !== '' &&
        previousParserId !== DocumentParserType.Regex
      ) {
        const currentRegexPattern = form.getValues(
          'parser_config.regex_pattern',
        );
        const currentDelimiter = form.getValues('parser_config.delimiter');
        // Set default regex_pattern if not already set
        if (!currentRegexPattern) {
          form.setValue('parser_config.regex_pattern', '[.!?]+\\s*');
        }
        // Set default delimiter for regex parser if not already set
        if (!currentDelimiter || currentDelimiter === '\n') {
          form.setValue('parser_config.delimiter', '\n。.；;！!？？');
        }
      }

      // Update previous parser ID
      if (selectedTag !== previousParserId) {
        setPreviousParserId(selectedTag);
      }
    } else if (selectedTag && selectedTag !== previousParserId) {
      // When switching from Regex to other parsers, clear regex_pattern and reset delimiter
      if (previousParserId === DocumentParserType.Regex) {
        // Clear regex_pattern as it's only used for regex parser
        form.setValue('parser_config.regex_pattern', undefined);
        // Reset delimiter to default newline
        const currentDelimiter = form.getValues('parser_config.delimiter');
        if (currentDelimiter === '\n。.；;！!？？') {
          form.setValue('parser_config.delimiter', '\n');
        }
      }

      // Update previous parser ID when parser changes
      setPreviousParserId(selectedTag);
    }
  }, [selectedTag, form, isDataLoaded, previousParserId]);
  return (
    <section className="p-5 h-full flex flex-col">
      <TopTitle
        title={t('knowledgeDetails.configuration')}
        description={t('knowledgeConfiguration.titleDescription')}
      ></TopTitle>
      <div className="flex gap-14 flex-1 min-h-0">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6 ">
            <div className="w-[768px] h-[calc(100vh-240px)] pr-1 overflow-y-auto scrollbar-auto">
              <MainContainer className="text-text-secondary">
                <GeneralForm></GeneralForm>
                <Divider />

                <GraphRagItems
                  className="border-none p-0"
                  data={graphRagGenerateData as IGenerateLogButtonProps}
                  onDelete={() =>
                    handleDeletePipelineTask(GenerateType.KnowledgeGraph)
                  }
                ></GraphRagItems>
                <Divider />
                <RaptorFormFields
                  data={raptorGenerateData as IGenerateLogButtonProps}
                  onDelete={() => handleDeletePipelineTask(GenerateType.Raptor)}
                ></RaptorFormFields>
                <Divider />
                <ParseTypeItem line={1} />
                {parseType === 1 && (
                  <ChunkMethodItem line={1}></ChunkMethodItem>
                )}
                {parseType === 2 && (
                  <DataFlowSelect
                    isMult={false}
                    showToDataPipeline={true}
                    formFieldName="pipeline_id"
                    layout={FormLayout.Horizontal}
                  />
                )}

                <Divider />
                {parseType === 1 && <ChunkMethodForm />}

                {/* <LinkDataPipeline
                  data={pipelineData}
                  handleLinkOrEditSubmit={handleLinkOrEditSubmit}
                /> */}
              </MainContainer>
            </div>
            <div className="text-right items-center flex justify-end gap-3 w-[768px]">
              <Button
                type="reset"
                className="bg-transparent text-color-white hover:bg-transparent border-gray-500 border-[1px]"
                onClick={() => {
                  form.reset();
                }}
              >
                {t('knowledgeConfiguration.cancel')}
              </Button>
              <SavingButton></SavingButton>
            </div>
          </form>
        </Form>
        <div className="flex-1">
          {parseType === 1 && <ChunkMethodLearnMore parserId={selectedTag} />}
        </div>
      </div>
    </section>
  );
}
