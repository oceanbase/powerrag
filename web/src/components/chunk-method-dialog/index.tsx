import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { DocumentParserType } from '@/constants/knowledge';
import { useFetchKnowledgeBaseConfiguration } from '@/hooks/use-knowledge-request';
import { IModalProps } from '@/interfaces/common';
import { IParserConfig } from '@/interfaces/database/document';
import { IChangeParserRequestBody } from '@/interfaces/request/document';
import {
  ChunkMethodItem,
  EnableTocToggle,
  ParseTypeItem,
} from '@/pages/dataset/dataset-setting/configuration/common-item';
import { zodResolver } from '@hookform/resolvers/zod';
import omit from 'lodash/omit';
import {} from 'module';
import { useEffect, useMemo } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';
import {
  AutoKeywordsFormField,
  AutoQuestionsFormField,
} from '../auto-keywords-form-field';
import { DataFlowSelect } from '../data-pipeline-select';
import { DelimiterFormField } from '../delimiter-form-field';
import { EntityTypesFormField } from '../entity-types-form-field';
import { ExcelToHtmlFormField } from '../excel-to-html-form-field';
import { FormContainer } from '../form-container';
import { LayoutRecognizeFormField } from '../layout-recognize-form-field';
import { MaxTokenNumberFormField } from '../max-token-number-from-field';
import { PdfParserFormField } from '../pdf-parser-form-field';
import { RegexPatternFormField } from '../regex-pattern-form-field';
import { TitleLevelFormField } from '../title-level-form-field';
import { ButtonLoading } from '../ui/button';
import { Input } from '../ui/input';
import { DynamicPageRange } from './dynamic-page-range';
import { useShowAutoKeywords } from './hooks';
import {
  useDefaultParserValues,
  useFillDefaultValueOnMount,
} from './use-default-parser-values';

const FormId = 'ChunkMethodDialogForm';

interface IProps extends IModalProps<IChangeParserRequestBody> {
  loading: boolean;
  parserId: string;
  pipelineId?: string;
  parserConfig: IParserConfig;
  documentExtension: string;
  documentId: string;
}

const hidePagesChunkMethods = [
  DocumentParserType.Qa,
  DocumentParserType.Table,
  DocumentParserType.Picture,
  DocumentParserType.Resume,
  DocumentParserType.One,
  DocumentParserType.KnowledgeGraph,
];

export function ChunkMethodDialog({
  hideModal,
  onOk,
  parserId,
  pipelineId,
  documentExtension,
  visible,
  parserConfig,
  loading,
  documentId,
}: IProps) {
  const { t } = useTranslation();

  const { data: knowledgeDetails } = useFetchKnowledgeBaseConfiguration();

  const useGraphRag = useMemo(() => {
    return knowledgeDetails.parser_config?.graphrag?.use_graphrag;
  }, [knowledgeDetails.parser_config?.graphrag?.use_graphrag]);

  const defaultParserValues = useDefaultParserValues(parserId);

  const fillDefaultParserValue = useFillDefaultValueOnMount();

  const FormSchema = z
    .object({
      parseType: z.number(),
      parser_id: z
        .string()
        .min(1, {
          message: t('common.pleaseSelect'),
        })
        .trim(),
      pipeline_id: z.string().optional(),
      parser_config: z.object({
        task_page_size: z.coerce.number().optional(),
        layout_recognize: z.string().optional(),
        pdf_parser: z.string().optional(),
        title_level: z.coerce.number().optional(),
        chunk_token_num: z.coerce.number().optional(),
        min_chunk_tokens: z.coerce.number().optional(),
        delimiter: z.string().optional(),
        regex_pattern: z.string().optional(),
        auto_keywords: z.coerce.number().optional(),
        auto_questions: z.coerce.number().optional(),
        html4excel: z.boolean().optional(),
        toc_extraction: z.boolean().optional(),
        // raptor: z
        //   .object({
        //     use_raptor: z.boolean().optional(),
        //     prompt: z.string().optional().optional(),
        //     max_token: z.coerce.number().optional(),
        //     threshold: z.coerce.number().optional(),
        //     max_cluster: z.coerce.number().optional(),
        //     random_seed: z.coerce.number().optional(),
        //   })
        //   .optional(),
        // graphrag: z.object({
        //   use_graphrag: z.boolean().optional(),
        // }),
        entity_types: z.array(z.string()).optional(),
        pages: z
          .array(z.object({ from: z.coerce.number(), to: z.coerce.number() }))
          .optional(),
      }),
    })
    .superRefine((data, ctx) => {
      if (data.parseType === 2 && !data.pipeline_id) {
        ctx.addIssue({
          path: ['pipeline_id'],
          message: t('common.pleaseSelect'),
          code: 'custom',
        });
      }
    });

  const form = useForm<z.infer<typeof FormSchema>>({
    resolver: zodResolver(FormSchema),
    defaultValues: {
      parser_id: parserId || '',
      pipeline_id: pipelineId || '',
      parseType: pipelineId ? 2 : 1,
      parser_config: defaultParserValues,
    },
  });

  const layoutRecognize = useWatch({
    name: 'parser_config.layout_recognize',
    control: form.control,
  });

  const selectedTag = useWatch({
    name: 'parser_id',
    control: form.control,
  });

  const isPdf = documentExtension === 'pdf';

  const showPages = useMemo(() => {
    return isPdf && hidePagesChunkMethods.every((x) => x !== selectedTag);
  }, [selectedTag, isPdf]);

  const showPdfParser = useMemo(() => {
    // Show PDF parser for Title and Smart parsers regardless of file type
    // For Regex, only show for PDF files
    return (
      selectedTag === DocumentParserType.Title ||
      selectedTag === DocumentParserType.Smart ||
      (isPdf && selectedTag === DocumentParserType.Regex)
    );
  }, [selectedTag, isPdf]);

  const showTitleLevel = useMemo(() => {
    return selectedTag === DocumentParserType.Title;
  }, [selectedTag]);

  const showOne = useMemo(() => {
    // Don't show LayoutRecognizeFormField if PdfParserFormField is shown (for title/regex/smart)
    if (showPdfParser) {
      return false;
    }
    return (
      isPdf &&
      hidePagesChunkMethods
        .filter((x) => x !== DocumentParserType.One)
        .every((x) => x !== selectedTag)
    );
  }, [selectedTag, isPdf, showPdfParser]);

  const showMaxTokenNumber =
    selectedTag === DocumentParserType.Naive ||
    selectedTag === DocumentParserType.KnowledgeGraph ||
    selectedTag === DocumentParserType.Regex ||
    selectedTag === DocumentParserType.Title ||
    selectedTag === DocumentParserType.Smart;

  const showEntityTypes = selectedTag === DocumentParserType.KnowledgeGraph;

  const showExcelToHtml =
    selectedTag === DocumentParserType.Naive && documentExtension === 'xlsx';

  const showAutoKeywords = useShowAutoKeywords();

  async function onSubmit(data: z.infer<typeof FormSchema>) {
    console.log('🚀 ~ onSubmit ~ data:', data);
    const parserConfig: any = { ...data.parser_config };
    // Remove pdf_parser field - PDF parser is stored in layout_recognize
    delete parserConfig.pdf_parser;

    // Handle Regex parser - remove pdf_parser and title_level
    if (data.parser_id === 'regex') {
      delete parserConfig.title_level;
    }

    const nextData: IChangeParserRequestBody = {
      parser_id: data.parser_id,
      pipeline_id: data.pipeline_id || '',
      doc_id: documentId,
      parser_config: {
        ...parserConfig,
        pages: data.parser_config?.pages?.map((x: any) => [x.from, x.to]) ?? [],
      },
    };
    console.log('🚀 ~ onSubmit ~ nextData:', nextData);
    const ret = await onOk?.(nextData);
    if (ret) {
      hideModal?.();
    }
  }

  useEffect(() => {
    if (visible) {
      const pages =
        parserConfig?.pages?.map((x) => ({ from: x[0], to: x[1] })) ?? [];
      form.reset({
        parser_id: parserId || '',
        pipeline_id: pipelineId || '',
        parseType: pipelineId ? 2 : 1,
        parser_config: fillDefaultParserValue(
          {
            pages: pages.length > 0 ? pages : [{ from: 1, to: 1024 }],
            ...omit(parserConfig, 'pages'),
            // graphrag: {
            //   use_graphrag: get(
            //     parserConfig,
            //     'graphrag.use_graphrag',
            //     useGraphRag,
            //   ),
            // },
          },
          parserId || '',
        ),
      });
    }
  }, [
    fillDefaultParserValue,
    form,
    knowledgeDetails.parser_config,
    parserConfig,
    parserId,
    pipelineId,
    useGraphRag,
    visible,
  ]);
  const parseType = useWatch({
    control: form.control,
    name: 'parseType',
    defaultValue: pipelineId ? 2 : 1,
  });
  useEffect(() => {
    if (parseType === 1) {
      form.setValue('pipeline_id', '');
    }
  }, [parseType, form]);

  // Set default values when Title or Regex parser is selected
  useEffect(() => {
    if (selectedTag === DocumentParserType.Title) {
      const currentTitleLevel = form.getValues('parser_config.title_level');
      if (!currentTitleLevel) {
        form.setValue('parser_config.title_level', 3);
      }
    } else if (selectedTag === DocumentParserType.Regex) {
      const currentRegexPattern = form.getValues('parser_config.regex_pattern');
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
  }, [selectedTag, form]);
  return (
    <Dialog open onOpenChange={hideModal}>
      <DialogContent className="max-w-[50vw] text-text-primary">
        <DialogHeader>
          <DialogTitle>{t('knowledgeDetails.chunkMethod')}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="space-y-6 max-h-[70vh] overflow-auto"
            id={FormId}
          >
            <FormContainer>
              <ParseTypeItem />
              {parseType === 1 && <ChunkMethodItem></ChunkMethodItem>}
              {parseType === 2 && (
                <DataFlowSelect
                  isMult={false}
                  // toDataPipeline={navigateToAgents}
                  formFieldName="pipeline_id"
                />
              )}

              {/* <FormField
                control={form.control}
                name="parser_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('knowledgeDetails.chunkMethod')}</FormLabel>
                    <FormControl>
                      <RAGFlowSelect
                        {...field}
                        options={parserList}
                      ></RAGFlowSelect>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              /> */}
              {showPages && parseType === 1 && (
                <DynamicPageRange></DynamicPageRange>
              )}
              {showPages && parseType === 1 && layoutRecognize && (
                <FormField
                  control={form.control}
                  name="parser_config.task_page_size"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel
                        tooltip={t('knowledgeDetails.taskPageSizeTip')}
                      >
                        {t('knowledgeDetails.taskPageSize')}
                      </FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          type={'number'}
                          min={1}
                          max={128}
                        ></Input>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}
            </FormContainer>
            {parseType === 1 && (
              <>
                <FormContainer
                  show={
                    showOne ||
                    showMaxTokenNumber ||
                    showPdfParser ||
                    showTitleLevel
                  }
                  className="space-y-3"
                >
                  {showPdfParser && <PdfParserFormField></PdfParserFormField>}
                  {showTitleLevel && (
                    <TitleLevelFormField></TitleLevelFormField>
                  )}
                  {showOne && (
                    <LayoutRecognizeFormField></LayoutRecognizeFormField>
                  )}
                  {showMaxTokenNumber && (
                    <>
                      <MaxTokenNumberFormField
                        max={
                          selectedTag === DocumentParserType.KnowledgeGraph
                            ? 8192 * 2
                            : 2048
                        }
                        initialValue={
                          selectedTag === DocumentParserType.Regex
                            ? 512
                            : selectedTag === DocumentParserType.Title ||
                                selectedTag === DocumentParserType.Smart
                              ? 256
                              : undefined
                        }
                      ></MaxTokenNumberFormField>
                      {selectedTag === DocumentParserType.Smart && (
                        <FormField
                          control={form.control}
                          name="parser_config.min_chunk_tokens"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel
                                tooltip={t(
                                  'knowledgeConfiguration.minChunkTokensDescription',
                                )}
                              >
                                {t('knowledgeConfiguration.minChunkTokens')}
                              </FormLabel>
                              <FormControl>
                                <Input
                                  type="number"
                                  min={32}
                                  max={1024}
                                  value={field.value as number}
                                  onChange={(e) =>
                                    field.onChange(Number(e.target.value))
                                  }
                                  onBlur={field.onBlur}
                                  name={field.name}
                                  ref={field.ref}
                                />
                              </FormControl>
                            </FormItem>
                          )}
                        />
                      )}
                      {selectedTag === DocumentParserType.Regex && (
                        <RegexPatternFormField />
                      )}
                      {(selectedTag === DocumentParserType.Naive ||
                        selectedTag === DocumentParserType.KnowledgeGraph ||
                        selectedTag === DocumentParserType.Regex ||
                        selectedTag === DocumentParserType.Title) && (
                        <DelimiterFormField></DelimiterFormField>
                      )}
                    </>
                  )}
                </FormContainer>
                <FormContainer
                  show={showAutoKeywords(selectedTag) || showExcelToHtml}
                  className="space-y-3"
                >
                  {selectedTag === DocumentParserType.Naive && (
                    <EnableTocToggle />
                  )}
                  {showAutoKeywords(selectedTag) && (
                    <>
                      <AutoKeywordsFormField></AutoKeywordsFormField>
                      <AutoQuestionsFormField></AutoQuestionsFormField>
                    </>
                  )}
                  {showExcelToHtml && (
                    <ExcelToHtmlFormField></ExcelToHtmlFormField>
                  )}
                </FormContainer>
                {/* {showRaptorParseConfiguration(
                  selectedTag as DocumentParserType,
                ) && (
                  <FormContainer>
                    <RaptorFormFields></RaptorFormFields>
                  </FormContainer>
                )} */}
                {/* {showGraphRagItems(selectedTag as DocumentParserType) &&
                  useGraphRag && (
                    <FormContainer>
                      <UseGraphRagFormField></UseGraphRagFormField>
                    </FormContainer>
                  )} */}
                {showEntityTypes && (
                  <EntityTypesFormField></EntityTypesFormField>
                )}
              </>
            )}
          </form>
        </Form>
        <DialogFooter>
          <ButtonLoading type="submit" form={FormId} loading={loading}>
            {t('common.save')}
          </ButtonLoading>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
