/** 工具结果分发组件 */

import type { ToolCall } from "../../types"
import PartAlternativeCard from "../tools/PartAlternativeCard"
import ManualStepCard from "../tools/ManualStepCard"
import VerificationResultCard from "../tools/VerificationResultCard"
import ImageParseCard from "../tools/ImageParseCard"

interface ToolResultCardProps {
  toolCalls: ToolCall[]
  userImage?: string
}

const ToolResultCard: React.FC<ToolResultCardProps> = ({ toolCalls, userImage }) => {
  return (
    <div className="space-y-2 my-2">
      {toolCalls.map((call, i) => {
        switch (call.name) {
          case "find_part_alternative":
            return <PartAlternativeCard key={i} data={call.result || call.args} />
          case "search_manual_step":
            return <ManualStepCard key={i} data={call.result || call.args} />
          case "verify_build_result":
            return (
              <VerificationResultCard
                key={i}
                data={call.result || call.args}
                userImage={userImage}
              />
            )
          case "parse_lego_image":
            return <ImageParseCard key={i} data={call.result || call.args} />
          default:
            return (
              <div key={i} className="rounded-lg border bg-muted/50 p-3 text-sm">
                <span className="text-muted-foreground">🔧 {call.name}</span>
              </div>
            )
        }
      })}
    </div>
  )
}

export default ToolResultCard
