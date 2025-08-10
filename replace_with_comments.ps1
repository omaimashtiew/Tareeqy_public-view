# تعليقات حسب نوع الملف
$comments = @{
    ".py" = "# This file is private and its content is not available here."
    ".js" = "// This file is private and its content is not available here."
    ".txt" = "# This file is private and its content is not available here."
    ".html" = "<!-- This file is private and its content is not available here. -->"
    ".css" = "/* This file is private and its content is not available here. */"
    ".json" = "// This file is private and its content is not available here."
    ".bat" = "REM This file is private and its content is not available here."
    ".sh" = "# This file is private and its content is not available here."
    ".sql" = "-- This file is private and its content is not available here."
    ".md" = "<!-- This file is private and its content is not available here. -->"
}

# مسار المشروع
$path = "C:\Tareeqy_public-view\tareeqy_tracker"

# اجلب كل الملفات النصية القابلة للتعديل داخل المجلد وكل الفروع
Get-ChildItem -Path $path -Recurse -File | ForEach-Object {
    $ext = $_.Extension.ToLower()
    if ($comments.ContainsKey($ext)) {
        $comment = $comments[$ext]
        # استبدل المحتوى بالتعليق المناسب
        Set-Content -Path $_.FullName -Value $comment -Encoding UTF8
        Write-Output "Processed file: $($_.FullName)"
    }
    else {
        Write-Output "Skipped file (no comment defined): $($_.FullName)"
    }
}
