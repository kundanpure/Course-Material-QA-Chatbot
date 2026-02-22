import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Copy, Check } from 'lucide-react';

interface MarkdownRendererProps {
    content: string;
}

function CodeBlock({ language, value }: { language: string; value: string }) {
    const [copied, setCopied] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="relative group my-3 rounded-lg overflow-hidden">
            {/* Header bar */}
            <div className="flex items-center justify-between bg-gray-800 px-4 py-2 text-xs text-gray-400">
                <span>{language || 'code'}</span>
                <button
                    onClick={handleCopy}
                    className="flex items-center space-x-1 hover:text-white transition-colors"
                >
                    {copied ? (
                        <>
                            <Check className="w-3.5 h-3.5" />
                            <span>Copied!</span>
                        </>
                    ) : (
                        <>
                            <Copy className="w-3.5 h-3.5" />
                            <span>Copy</span>
                        </>
                    )}
                </button>
            </div>
            {/* Code content */}
            <SyntaxHighlighter
                style={oneDark}
                language={language || 'text'}
                PreTag="div"
                customStyle={{
                    margin: 0,
                    borderRadius: 0,
                    fontSize: '0.8rem',
                }}
            >
                {value}
            </SyntaxHighlighter>
        </div>
    );
}

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
    return (
        <div className="markdown-body text-sm leading-relaxed">
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    // Code blocks with copy button
                    code({ node, className, children, ...props }) {
                        const match = /language-(\w+)/.exec(className || '');
                        const isInline = !match && !String(children).includes('\n');

                        if (!isInline) {
                            return (
                                <CodeBlock
                                    language={match ? match[1] : ''}
                                    value={String(children).replace(/\n$/, '')}
                                />
                            );
                        }
                        return (
                            <code
                                className="bg-gray-100 dark:bg-dark-700 px-1.5 py-0.5 rounded text-xs font-mono text-primary-600 dark:text-primary-400"
                                {...props}
                            >
                                {children}
                            </code>
                        );
                    },
                    // Headers
                    h1: ({ children }) => (
                        <h1 className="text-xl font-bold mt-4 mb-2 text-gray-900 dark:text-white">{children}</h1>
                    ),
                    h2: ({ children }) => (
                        <h2 className="text-lg font-bold mt-4 mb-2 text-gray-900 dark:text-white">{children}</h2>
                    ),
                    h3: ({ children }) => (
                        <h3 className="text-base font-semibold mt-3 mb-1 text-gray-800 dark:text-gray-200">{children}</h3>
                    ),
                    // Paragraphs
                    p: ({ children }) => (
                        <p className="mb-2 text-gray-700 dark:text-gray-300">{children}</p>
                    ),
                    // Lists
                    ul: ({ children }) => (
                        <ul className="list-disc list-inside mb-2 space-y-1 text-gray-700 dark:text-gray-300">{children}</ul>
                    ),
                    ol: ({ children }) => (
                        <ol className="list-decimal list-inside mb-2 space-y-1 text-gray-700 dark:text-gray-300">{children}</ol>
                    ),
                    li: ({ children }) => (
                        <li className="ml-2">{children}</li>
                    ),
                    // Bold text
                    strong: ({ children }) => (
                        <strong className="font-semibold text-gray-900 dark:text-white">{children}</strong>
                    ),
                    // Tables
                    table: ({ children }) => (
                        <div className="overflow-x-auto my-3">
                            <table className="min-w-full text-xs border border-gray-200 dark:border-dark-700 rounded-lg overflow-hidden">
                                {children}
                            </table>
                        </div>
                    ),
                    thead: ({ children }) => (
                        <thead className="bg-gray-100 dark:bg-dark-700">{children}</thead>
                    ),
                    th: ({ children }) => (
                        <th className="px-3 py-2 text-left font-semibold text-gray-700 dark:text-gray-300 border-b border-gray-200 dark:border-dark-600">{children}</th>
                    ),
                    td: ({ children }) => (
                        <td className="px-3 py-2 border-b border-gray-100 dark:border-dark-700">{children}</td>
                    ),
                    // Blockquotes
                    blockquote: ({ children }) => (
                        <blockquote className="border-l-4 border-primary-400 pl-4 my-2 italic text-gray-600 dark:text-gray-400">{children}</blockquote>
                    ),
                    // Horizontal rule
                    hr: () => <hr className="my-3 border-gray-200 dark:border-dark-700" />,
                    // Links
                    a: ({ href, children }) => (
                        <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary-600 dark:text-primary-400 hover:underline">{children}</a>
                    ),
                }}
            >
                {content}
            </ReactMarkdown>
        </div>
    );
};

export default MarkdownRenderer;
