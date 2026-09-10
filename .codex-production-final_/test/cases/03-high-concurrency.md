# Case: High concurrent mix

One burst of 10: text, pdf, txt, md, docx, xlsx, pptx, image, audio, video.

Record count, start/end, success/fail, latency, queue, timeouts, exceptions, drops.

Then **ramp until fail**: increase concurrent text until the first failure. Record last all-success N and first-fail N.

Run 1 and Run 2 use different fixture text/files.
