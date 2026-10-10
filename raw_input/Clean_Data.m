%% This script is used to clean the AFLUX data

% delete high entropy alloys data points
% generate sub-group for high entropy oxide by element types

clear;
close all;
clc

%% Input the file names

file_name1 = 'data_1002.xlsx'; 
file_name2 = 'data_1002_delete_alloys.xlsx'; 

sheet_1 = 'DFT properties';
sheet_2 = 'ele descriptors';

%% Import raw data

[raw_num_1,raw_text_1] = xlsread(file_name1, sheet_1);
[raw_num_2,raw_text_2] = xlsread(file_name1, sheet_2);
%raw_data_2 = readmatrix(file_name1, 'Sheet', sheet_2);

name_1 = raw_text_1(2:end,1);
name_2 = raw_text_2(2:end,1);
Var_1 = raw_text_1(1,2:end);
Var_2 = raw_text_2(1,2:end);

%% Clean raw data to get high entropy oxide discriptor sheet 1

cF8_225_name_1 = cell(size(name_1));
cF8_225_num_1 = zeros(size(raw_num_1));
cF88_227_name_1 = cell(size(name_1));
cF88_227_num_1 = zeros(size(raw_num_1));
idx1 = 1;
idx2 = 1;
idx3 = 0;
for i = 1:1:length(name_1)

    tline = name_1{i}; 
    if ~isempty(regexpi(tline, 'POCC_P0-1x')>0) && ~isempty(regexpi(tline, 'cF8_225')>0)

        cF8_225_name_1{idx1} = tline;
        cF8_225_num_1(idx1,:) = raw_num_1(i,:);
        idx1 = idx1 + 1;

    end

    if  ~isempty(regexpi(tline, 'cF88_227')>0)
        %if ~isempty(regexpi(tline, '_pvO')>0) || ~isempty(regexpi(tline, '_svO')>0)

            cF88_227_name_1{idx2} = tline;
            cF88_227_num_1(idx2,:) = raw_num_1(i,:);
            idx2 = idx2 + 1;

       % end
    end

    if ~isempty(regexpi(tline, 'cI2_229')>0) || ~isempty(regexpi(tline, 'cF4_225')>0)

        idx3 = idx3 + 1;

    end    

end
cF8_225_name_1(idx1:end,:) = [];
cF8_225_num_1(idx1:end,:) = [];
cF88_227_name_1(idx2:end,:) = [];
cF88_227_num_1(idx2:end,:) = [];

HEO_name_1 = [cF8_225_name_1; cF88_227_name_1];
HEO_num_1 = [cF8_225_num_1; cF88_227_num_1];

%% Clean raw data to get high entropy oxide discriptor sheet 2

cF8_225_name_2 = cell(size(name_2));
cF8_225_num_2 = zeros(size(raw_num_2));
cF88_227_name_2 = cell(size(name_2));
cF88_227_num_2 = zeros(size(raw_num_2));
idx1 = 1;
idx2 = 1;
idx3 = 0;
for i = 1:1:length(name_2)

    tline = name_2{i}; 
    if ~isempty(regexpi(tline, 'POCC_P0-1x')>0) && ~isempty(regexpi(tline, 'cF8_225')>0)

        cF8_225_name_2{idx1} = tline;
        cF8_225_num_2(idx1,:) = raw_num_2(i,:);
        idx1 = idx1 + 1;
        
    end

    if  ~isempty(regexpi(tline, 'cF88_227')>0)
        %if ~isempty(regexpi(tline, '_pvO')>0) || ~isempty(regexpi(tline, '_svO')>0)

            cF88_227_name_2{idx2} = tline;
            cF88_227_num_2(idx2,:) = raw_num_2(i,:);
            idx2 = idx2 + 1;

       % end
    end

    if ~isempty(regexpi(tline, 'cI2_229')>0) || ~isempty(regexpi(tline, 'cF4_225')>0)

        idx3 = idx3 + 1;

    end    

end
cF8_225_name_2(idx1:end,:) = [];
cF8_225_num_2(idx1:end,:) = [];
cF88_227_name_2(idx2:end,:) = [];
cF88_227_num_2(idx2:end,:) = [];

HEO_name_2 = [cF8_225_name_2; cF88_227_name_2];
HEO_num_2 = [cF8_225_num_2; cF88_227_num_2];

save("data_1002_delete_alloys.mat","HEO_name_1","HEO_num_1","HEO_name_2","HEO_num_2");

%% Write data into a Excel file

T1 = cell2table(raw_text_1(1,:));
% xlswrite(file_name2,raw_text_1(1,:),sheet_1,'A1');
writetable(T1, file_name2, ...
           'Sheet', sheet_1, ...
           'Range', 'A1', ...
           'WriteVariableNames', false);   % 不写入列标题

T2 = cell2table(HEO_name_1);
% xlswrite(file_name2,HEO_name_1,sheet_1,'A2');
writetable(T2, file_name2, ...
           'Sheet', sheet_1, ...
           'Range', 'A2', ...
           'WriteVariableNames', false);   % 不写入列标题

T3 = array2table(HEO_num_1);
% xlswrite(file_name2,HEO_num_1,sheet_1,'B2');
writetable(T3, file_name2, ...
           'Sheet', sheet_1, ...
           'Range', 'B2', ...
           'WriteVariableNames', false);   % 不写入列标题

T4 = cell2table(raw_text_2(1,:));
% xlswrite(file_name2,raw_text_2(1,:),sheet_2,'A1');
writetable(T4, file_name2, ...
           'Sheet', sheet_2, ...
           'Range', 'A1', ...
           'WriteVariableNames', false);   % 不写入列标题

T5 = cell2table(HEO_name_2);
% xlswrite(file_name2,HEO_name_2,sheet_2,'A2');
writetable(T5, file_name2, ...
           'Sheet', sheet_2, ...
           'Range', 'A2', ...
           'WriteVariableNames', false);   % 不写入列标题

T6 = array2table(HEO_num_2);
% xlswrite(file_name2,HEO_num_2,sheet_2,'B2');
writetable(T6, file_name2, ...
           'Sheet', sheet_2, ...
           'Range', 'B2', ...
           'WriteVariableNames', false);   % 不写入列标题





