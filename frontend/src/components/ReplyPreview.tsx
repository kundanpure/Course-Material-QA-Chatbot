import React from "react";

interface Props {
  replyTo: any;
  onCancel: () => void;
}

export default function ReplyPreview({ replyTo, onCancel }: Props) {
  if (!replyTo) return null;

  return (
    <div className="bg-gray-100 border-l-4 border-blue-500 p-2 mb-2 flex justify-between items-center rounded">
      <div className="text-sm">
        <div className="font-semibold text-xs text-gray-500">
          Replying to
        </div>
        <div className="text-xs text-gray-700 truncate max-w-[300px]">
          {replyTo.content}
        </div>
      </div>

      <button
        onClick={onCancel}
        className="text-red-500 text-sm font-bold"
      >
        ✕
      </button>
    </div>
  );
}