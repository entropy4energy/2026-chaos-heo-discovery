% MATLAB 代码：处理上传的 Excel 文件，提取每个材料的四种金属元素名称
% 作者：Grok（基于用户需求生成）
% 使用说明：
%   1. 将此代码保存为 .m 文件（例如 extract_metals.m）
%   2. 确保 MATLAB 当前工作目录能访问该 Excel 文件，或者修改 filename 为完整路径
%   3. 运行该脚本即可自动生成新 Excel 文件
%   4. 新文件名为 extracted_metals.xlsx，每一行对应原始数据的顺序，包含四列金属元素（Metal1~Metal4）
%      - 如果某个材料金属元素少于4种，后面的列为空
%      - 如果多于4种，只取前4种（按字符串中出现的顺序）

clear; clc;

% ==================== 1. 设置文件路径 ====================
% 请根据实际情况修改为你的 Excel 文件完整路径
filename = 'data_1002_delete_cf88_227.xlsx';
% 如果在本地运行，可以改为相对路径，例如：
% filename = 'data_1002_delete_cf88_227.xlsx';

% ==================== 2. 读取 DFT properties sheet 的第一列 name 数据 ====================
% 使用 readcell 读取从第2行开始（跳过表头），第一列的所有 name
names = readcell(filename, 'Sheet', 'DFT_properties', 'Range', 'A2:A10000');

% 移除可能的空单元格（保险起见）
names = names(~cellfun(@(x) isempty(x) || ~ischar(x) && ~isstring(x), names));

fprintf('成功读取 %d 条 name 数据。\n', length(names));

% ==================== 3. 准备输出：四列字符串矩阵（cell array） ====================
num_rows = length(names);
metals_cell = cell(num_rows, 4);   % 4列：Metal1, Metal2, Metal3, Metal4

% ==================== 4. 逐行解析金属元素 ====================
for i = 1:num_rows
    name = names{i};
    
    % 取 ":PAW_PBE" 之前部分
    if contains(name, ':PAW_PBE')
        comp_part = extractBefore(name, ':PAW_PBE');
    else
        comp_part = name;
    end
    
    % 匹配所有元素（支持 Ca_sv、Cd、Fe_pv 等）
    tokens = regexp(comp_part, '[A-Z][a-z]?(_pv|_sv)?', 'match');
    
    metal_list = {};
    for t = 1:length(tokens)
        token = tokens{t};
        
        % 提取纯元素符号（修复版：不再使用 'once'）
        el_matches = regexp(token, '^[A-Z][a-z]?', 'match');
        if ~isempty(el_matches)
            el = el_matches{1};          % 现在一定是 cell → 安全
            if ~strcmp(el, 'O')
                metal_list{end+1} = el;
            end
        end
    end
    
    % 只保留前4个金属元素
    for j = 1:min(4, length(metal_list))
        metals_cell{i, j} = metal_list{j};
    end
end
% ==================== 5. 创建表格并保存为新 Excel 文件 ====================
T = cell2table(metals_cell, ...
    'VariableNames', {'Metal1', 'Metal2', 'Metal3', 'Metal4'});

output_filename = 'extracted_metals.xlsx';
writetable(T, output_filename);

fprintf('处理完成！已将四种金属元素保存到新文件：%s\n', output_filename);
fprintf('共处理 %d 行数据，每行对应原始 Excel 的顺序。\n', num_rows);

% ==================== 可选：显示前5行结果（便于检查） ====================
disp('前5行结果预览：');
disp(T(1:min(5, num_rows), :));

% ==================== 结束 ====================
% 如果需要同时保存原始 name，可以取消下面注释：
% T_with_name = [table(names, 'VariableNames', {'Original_Name'}), T];
% writetable(T_with_name, 'extracted_metals_with_name.xlsx');