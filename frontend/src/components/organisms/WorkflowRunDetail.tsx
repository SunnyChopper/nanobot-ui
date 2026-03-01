import { ExternalLink } from 'lucide-react'
import { RunStepsTimeline } from '../molecules/RunStepsTimeline'
import type { WorkflowRun, WorkflowRunStep } from '../../api/workflows'

const LANGSMITH_BASE = 'https://smith.langchain.com'

interface WorkflowRunDetailProps {
  run: WorkflowRun
}

export function WorkflowRunDetail({ run }: WorkflowRunDetailProps) {
  const hasError = run.status === 'error' && (run.error_message || run.error_node)
  const steps = run.result_envelope?.steps as WorkflowRunStep[] | undefined

  return (
    <div className="space-y-2 text-xs">
      {run.input_snapshot && Object.keys(run.input_snapshot).length > 0 && (
        <div>
          <span className="text-zinc-500 font-medium">Input</span>
          <pre className="mt-0.5 p-2 rounded bg-zinc-800/80 text-zinc-400 overflow-x-auto whitespace-pre-wrap break-words">
            {JSON.stringify(run.input_snapshot, null, 2)}
          </pre>
        </div>
      )}
      {steps && steps.length > 0 && <RunStepsTimeline steps={steps} />}
      {hasError && (
        <>
          {run.error_node && (
            <p>
              <span className="text-zinc-500">Failed node:</span>{' '}
              <span className="font-mono text-red-400">{run.error_node}</span>
            </p>
          )}
          {run.error_message && (
            <div>
              <span className="text-zinc-500 font-medium">Error</span>
              <p className="mt-0.5 p-2 rounded bg-red-900/20 text-red-300 whitespace-pre-wrap break-words">
                {run.error_message}
              </p>
            </div>
          )}
          {run.error_detail?.stack_trace && (
            <div>
              <span className="text-zinc-500 font-medium">Stack trace</span>
              <pre className="mt-0.5 p-2 rounded bg-zinc-800/80 text-zinc-500 overflow-x-auto text-[10px] whitespace-pre-wrap break-words max-h-40 overflow-y-auto">
                {run.error_detail.stack_trace}
              </pre>
            </div>
          )}
          {run.error_detail?.node_input_snapshot &&
            Object.keys(run.error_detail.node_input_snapshot).length > 0 && (
              <div>
                <span className="text-zinc-500 font-medium">Node input at failure</span>
                <pre className="mt-0.5 p-2 rounded bg-zinc-800/80 text-zinc-400 overflow-x-auto whitespace-pre-wrap break-words">
                  {JSON.stringify(run.error_detail.node_input_snapshot, null, 2)}
                </pre>
              </div>
            )}
        </>
      )}
      {run.result_envelope &&
        run.status === 'success' &&
        !(steps && steps.length > 0) &&
        Object.keys(run.result_envelope).length > 0 && (
          <div>
            <span className="text-zinc-500 font-medium">Result</span>
            <pre className="mt-0.5 p-2 rounded bg-zinc-800/80 text-zinc-400 overflow-x-auto whitespace-pre-wrap break-words max-h-32 overflow-y-auto">
              {JSON.stringify(run.result_envelope, null, 2)}
            </pre>
          </div>
        )}
      {run.result_envelope &&
        run.status === 'success' &&
        (steps?.length ?? 0) > 0 && (
          <div>
            <span className="text-zinc-500 font-medium">Final result</span>
            <pre className="mt-0.5 p-2 rounded bg-zinc-800/80 text-zinc-400 overflow-x-auto whitespace-pre-wrap break-words max-h-32 overflow-y-auto">
              {typeof run.result_envelope.last_output === 'string'
                ? run.result_envelope.last_output
                : JSON.stringify(run.result_envelope, null, 2)}
            </pre>
          </div>
        )}
      {run.langsmith_run_id && (
        <a
          href={`${LANGSMITH_BASE}/o/default/runs/${run.langsmith_run_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-blue-400 hover:underline"
        >
          <ExternalLink size={12} />
          Open in LangSmith
        </a>
      )}
    </div>
  )
}
