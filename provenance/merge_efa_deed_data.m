% MATLAB代码：处理上传的两个Excel文件，按要求匹配金属元素并合并数据
% 严格按照您的任务要求实现：
% 1. 读取 chaos_data.xlsx 的 Sheet1 到 chaos_data (cell 矩阵)
% 2. 读取 lib5_efa_deed.xlsx 的 cleaned sheet (若不存在则 fallback 到 raw) 到 efa_deed
% 3-4. 逐行循环 chaos_data，使用 B-E 列的 4 种金属元素（排序后忽略顺序）匹配 efa_deed 的 A-D 列
% 5-6. 找到匹配后，将 efa_deed E-I 列数据添加到 chaos_data 的 AL-AP 列（第38-42列）；
%      AQ列（43）记录 efa_deed 原始行号；AR列（44）标记匹配情况（1=唯一匹配，2=多个匹配）
%      无匹配则删除该行
% 7. 保存更新后的数据到新的 Excel 文件

clear; clc;

% ====================== 1. 读取 chaos_data.xlsx ======================
chaos_file = 'chaos_data.xlsx';
chaos_data = readcell(chaos_file, 'Sheet', 'Sheet1');

% ====================== 2. 读取 lib5_efa_deed.xlsx ======================
lib_file = 'lib5_efa_deed.xlsx';

% 优先使用您指定的 'cleaned' sheet，如果不存在则 fallback 到 'raw' 或第一个 sheet
sheets = sheetnames(lib_file);
if ismember('cleaned', sheets)
    efa_sheet = 'cleaned';
    fprintf('使用 sheet: cleaned\n');
elseif ismember('raw', sheets)
    efa_sheet = 'raw';
    fprintf('cleaned sheet 不存在，使用 sheet: raw\n');
else
    efa_sheet = sheets{1};
    fprintf('使用第一个 sheet: %s\n', efa_sheet);
end
efa_deed = readcell(lib_file, 'Sheet', efa_sheet);

% ====================== 参数准备 ======================
num_chaos = size(chaos_data, 1);
num_efa   = size(efa_deed, 1);

% chaos_data 原有列数应为 37 列（AL=38）
original_cols = size(chaos_data, 2);
fprintf('chaos_data 读取完成：%d 行 × %d 列\n', num_chaos, original_cols);
fprintf('efa_deed 读取完成：%d 行 × %d 列（sheet: %s）\n', num_efa, size(efa_deed, 2), efa_sheet);

% ====================== 处理循环 ======================
output = [chaos_data, cell(num_chaos, 7)];  % 扩展 7 列：AL-AP (5列) + AQ + AR

keep = true(num_chaos, 1);
keep(1) = true;  % 保留表头

for i = 2:num_chaos
    % 获取 chaos_data 的 4 种金属 (B-E 列，索引 2:5)
    metals_chaos = chaos_data(i, 2:5);
    % 去除可能的空值
    metals_chaos = metals_chaos(~cellfun(@(x) isempty(x) || (ischar(x) && strtrim(x)==""), metals_chaos));
    
    if length(metals_chaos) ~= 4
        keep(i) = false;
        continue;
    end
    
    % 排序用于忽略顺序匹配
    sorted_chaos = sort(metals_chaos);
    
    % 在 efa_deed 中查找匹配 (A-D 列，索引 1:4)
    match_indices = [];
    for j = 2:num_efa
        metals_efa = efa_deed(j, 1:4);
        metals_efa = metals_efa(~cellfun(@(x) isempty(x) || (ischar(x) && strtrim(x)==""), metals_efa));
        
        if length(metals_efa) == 4
            sorted_efa = sort(metals_efa);
            if isequal(sorted_chaos, sorted_efa)
                match_indices = [match_indices; j];
            end
        end
    end
    
    num_matches = length(match_indices);
    
    if num_matches == 0
        keep(i) = false;  % 无匹配 → 删除该行
    else
        % 有匹配 → 使用第一个匹配的结果填充数据
        j_match = match_indices(1);
        
        % E-I 列 (efa_deed 第 5-9 列) 添加到 AL-AP (output 第 38-42 列)
        efa_ei_data = efa_deed(j_match, 5:9);
        output(i, 38:42) = efa_ei_data;
        
        % AQ 列 (第 43 列)：efa_deed 原始行号
        output(i, 43) = {j_match};
        
        % AR 列 (第 44 列)：匹配数量标记 (1=唯一, >=2=多个)
        output(i, 44) = {num_matches};
        
        keep(i) = true;
    end
end

% ====================== 保留有效行并更新表头 ======================
output = output(keep, :);

% 为新增列添加有意义的表头（可选但推荐）
if size(output, 2) >= 44
    output(1, 38:44) = {'EFA', 'DEED', 'd2h', 'deed_cce', 'EFA_cce', 'efa_original_row', 'match_count'};
end

% ====================== 关键修复：处理 missing 值 ======================
% MATLAB 不支持 ? : 三元运算符，这里使用兼容写法
for k = 1:numel(output)
    if ismissing(output{k})
        output{k} = '';
    end
end

% ====================== 7. 保存新 Excel ======================
output_file = 'chaos_data_with_efa_deed.xlsx';
writecell(output, output_file, 'Sheet', 'Sheet1');

% ====================== 完成提示 ======================
fprintf('\n=== 处理完成！===\n');
fprintf('原始 chaos_data 有效数据行数: %d\n', num_chaos - 1);
fprintf('匹配并保留的数据行数: %d\n', sum(keep) - 1);
fprintf('结果已保存到新文件: %s\n', output_file);
fprintf('新增列说明：\n');
fprintf('   AL-AP (38-42列) ← efa_deed 的 E-I 列数据\n');
fprintf('   AQ (43列)       ← efa_deed 中对应材料的原始行号\n');
fprintf('   AR (44列)       ← 1 表示唯一匹配，2 表示多个匹配\n');
fprintf('非匹配行已被自动删除。\n');